"""Jembatan sync untuk tool `search_module`: `ai-services/clarifier/agent.py` menjalankan loop tool
calling secara sinkron (lewat `asyncio.to_thread`, lihat services.py), jadi butuh cara mengakses
pgvector tanpa AsyncSession yang terikat ke event loop pemanggil. Dipisah pakai `psycopg` (sync,
sudah jadi dependency project) khusus untuk hot-path ini -- CRUD sesi/pesan chat tetap lewat
`ChatbotRepository` (AsyncSession) seperti domain lain.

Retrieval di-scope ke CLASSROOM (lintas semua chapter published di situ), bukan satu chapter_id --
similarity tertinggi di antara hasil juga dipakai langsung sebagai sinyal scope gate di `agent.py`/`scope_gate.py`,
jadi tidak perlu anchor topik statis per-chapter lagi.

Juga jadi tempat 2 lapis cache Redis:
- query embedding cache -- pertanyaan sama = vector sama, TTL panjang
- retrieval cache -- top-k per (classroom_id, query), TTL pendek (bukan diikat ke kb_version lagi
  karena satu classroom bisa punya banyak chapter dengan versi reindex berbeda-beda -- cukup
  andalkan TTL pendek untuk stale-proofing, trade-off yang wajar dibanding melacak versi gabungan)
"""

from __future__ import annotations

import hashlib
import json

import psycopg
import redis
from pgvector import Vector
from pgvector.psycopg import register_vector

from app.core.config import settings
from app.utils import paths

paths.setup()
from clarifier import config as ai_config
from clarifier import formula_text
from clarifier import fusion
from clarifier import lexical
from clarifier import llm_ext

_redis_sync = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

SEARCH_VERSION = "hybrid-v3"
CANDIDATES = 20
MAX_TOKEN_DOCUMENT_FREQUENCY = 0.1
MIN_TOKEN_DOCUMENT_ALLOWANCE = 2
DENSE_WEIGHT, LEXICAL_WEIGHT, FORMULA_WEIGHT = 1.0, 0.25, 2.0
_PUBLISHED_CHUNKS = """
FROM block_embeddings be
JOIN chapters c ON c.id = be.chapter_id
JOIN modules m ON m.id = c.module_id
WHERE m.classroom_id = %s AND lower(m.status::text) = 'publish'
"""


def _sync_dsn() -> str:
    """`settings.DB_URL` dipakai asyncpg (`postgresql+asyncpg://...`); psycopg butuh DSN polos."""
    return settings.DB_URL.replace("+asyncpg", "")


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def embed_cached(text: str) -> list[float]:
    key = f"chatbot:emb:{_hash(text, ai_config.EMBEDDING_MODEL)}"
    cached = _redis_sync.get(key)
    if cached is not None:
        return json.loads(cached)
    vector = llm_ext.embed_text(text)
    _redis_sync.setex(key, settings.QUERY_EMBEDDING_CACHE_TTL_SECONDS, json.dumps(vector))
    return vector


def search_similar_chunks_cached(classroom_id: int, query: str, top_k: int) -> list[dict]:
    """Cari chunk lintas SEMUA chapter published di classroom ini dengan tiga daftar kandidat (vektor,
    kata kunci, kecocokan rumus persis) yang digabung RRF. Tiap hasil tetap bawa `similarity` (1 - cosine
    distance) -- sinyal scope gate (nilai tertinggi) di pemanggil, bukan urutan hasil."""
    key = f"chatbot:retr:{SEARCH_VERSION}:{classroom_id}:{top_k}:{_hash(query)}"
    cached = _redis_sync.get(key)
    if cached is not None:
        return json.loads(cached)

    query_embedding = Vector(embed_cached(query))
    with psycopg.connect(_sync_dsn()) as conn:
        register_vector(conn)
        dense = _dense_ids(conn, classroom_id, query_embedding)
        weighted = [
            (weight, ranking) for weight, ranking in (
                (DENSE_WEIGHT, dense),
                (LEXICAL_WEIGHT, _lexical_ids(conn, classroom_id, lexical.lexical_tokens(query))),
                (FORMULA_WEIGHT, _formula_ids(conn, classroom_id, formula_text.formula_spans(query))),
            ) if ranking
        ]
        fused = fusion.reciprocal_rank_fusion([ranking for _, ranking in weighted], [weight for weight, _ in weighted], limit=top_k)
        if dense and dense[0] not in fused:
            fused = [*fused[:max(top_k - 1, 0)], dense[0]]
        rows = _fetch_rows(conn, fused, query_embedding)

    results = [
        {
            # `reference` = block_ids[0] (BUKAN block_embeddings.id) -- 1 chunk = 1 block, jadi
            # tidak ada alasan 2 penomoran beda hidup berdampingan. Model kemarin ketuker milih
            # block_ids alih-alih reference karena dua-duanya sama-sama "angka block" yang masuk
            # akal buat mereka -- sekarang keduanya SELALU sama, ketuker atau tidak hasilnya benar.
            "reference": str(row[1][0]),
            "block_ids": row[1],
            "heading": row[2],
            "text": row[3],
            "chapter_id": row[4],
            "similarity": float(row[5]),
        }
        for row in rows
    ]
    _redis_sync.setex(key, settings.RETRIEVAL_CACHE_TTL_SECONDS, json.dumps(results))
    return results


def _dense_ids(conn, classroom_id: int, query_embedding: Vector) -> list[int]:
    rows = conn.execute(
        f"SELECT be.id {_PUBLISHED_CHUNKS} ORDER BY be.embedding <=> %s LIMIT %s",
        (classroom_id, query_embedding, CANDIDATES),
    ).fetchall()
    return [row[0] for row in rows]


def _rare_tokens(conn, classroom_id: int, tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    filters = ", ".join("count(*) FILTER (WHERE be.lexical_tsv @@ to_tsquery('simple', %s))" for _ in tokens)
    counts = conn.execute(f"SELECT count(*), {filters} {_PUBLISHED_CHUNKS}", (*tokens, classroom_id)).fetchone()
    total = counts[0] or 1
    return [token for token, count in zip(tokens, counts[1:]) if 0 < count <= max(MIN_TOKEN_DOCUMENT_ALLOWANCE, total * MAX_TOKEN_DOCUMENT_FREQUENCY)]


def _lexical_ids(conn, classroom_id: int, tokens: list[str]) -> list[int]:
    tsquery = " | ".join(_rare_tokens(conn, classroom_id, tokens))
    if not tsquery:
        return []
    rows = conn.execute(
        f"""
        SELECT be.id {_PUBLISHED_CHUNKS} AND be.lexical_tsv @@ to_tsquery('simple', %s)
        ORDER BY ts_rank_cd(be.lexical_tsv, to_tsquery('simple', %s)) DESC LIMIT %s
        """,
        (classroom_id, tsquery, tsquery, CANDIDATES),
    ).fetchall()
    return [row[0] for row in rows]


def _formula_ids(conn, classroom_id: int, spans: list[str]) -> list[int]:
    if not spans:
        return []
    matches = " + ".join("(position(%s in be.formula_norm) > 0)::int" for _ in spans)
    rows = conn.execute(
        f"""
        SELECT be.id {_PUBLISHED_CHUNKS} AND ({matches}) > 0
        ORDER BY ({matches}) DESC, length(be.formula_norm) ASC LIMIT %s
        """,
        (classroom_id, *spans, *spans, CANDIDATES),
    ).fetchall()
    return [row[0] for row in rows]


def _fetch_rows(conn, ordered_ids: list[int], query_embedding: Vector) -> list[tuple]:
    if not ordered_ids:
        return []
    rows = conn.execute(
        """
        SELECT be.id, be.block_ids, be.heading, be.chunk_text, be.chapter_id, 1 - (be.embedding <=> %s) AS similarity
        FROM block_embeddings be WHERE be.id = ANY(%s)
        """,
        (query_embedding, ordered_ids),
    ).fetchall()
    by_id = {row[0]: row for row in rows}
    return [by_id[chunk_id] for chunk_id in ordered_ids if chunk_id in by_id]


def make_search_module_executor(classroom_id: int, top_k: int):
    def executor(query: str) -> list[dict]:
        return search_similar_chunks_cached(classroom_id, query, top_k)

    return executor
