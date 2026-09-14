"""Jembatan sync untuk tool `search_module`: `ai-services/chatbot/agent.py` menjalankan loop tool
calling secara sinkron (lewat `asyncio.to_thread`, lihat services.py), jadi butuh cara mengakses
pgvector tanpa AsyncSession yang terikat ke event loop pemanggil. Dipisah pakai `psycopg` (sync,
sudah jadi dependency project) khusus untuk hot-path ini -- CRUD sesi/pesan chat tetap lewat
`ChatbotRepository` (AsyncSession) seperti domain lain.

Retrieval di-scope ke CLASSROOM (lintas semua chapter published di situ), bukan satu chapter_id --
similarity hasil top-1 juga dipakai langsung sebagai sinyal scope gate di `agent.py`/`scope_gate.py`,
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
import config as ai_config  # noqa: E402  (ai-services/annotation/config.py, via paths.setup())
import llm_ext  # noqa: E402  (ai-services/chatbot/llm_ext.py)

_redis_sync = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


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
    """Cari chunk paling mirip lintas SEMUA chapter published di classroom ini. Tiap hasil bawa
    `similarity` (1 - cosine distance) -- dipakai baik sebagai konten tool `search_module` maupun
    sebagai sinyal scope gate (skor top-1) di pemanggil."""
    key = f"chatbot:retr:{classroom_id}:{_hash(query)}"
    cached = _redis_sync.get(key)
    if cached is not None:
        return json.loads(cached)

    query_embedding = Vector(embed_cached(query))
    with psycopg.connect(_sync_dsn()) as conn:
        register_vector(conn)
        rows = conn.execute(
            """
            SELECT be.id, be.block_ids, be.heading, be.chunk_text, be.chapter_id,
                   1 - (be.embedding <=> %s) AS similarity
            FROM block_embeddings be
            JOIN chapters c ON c.id = be.chapter_id
            JOIN modules m ON m.id = c.module_id
            WHERE m.classroom_id = %s AND lower(m.status::text) = 'publish'
            ORDER BY be.embedding <=> %s
            LIMIT %s
            """,
            (query_embedding, classroom_id, query_embedding, top_k),
        ).fetchall()

    results = [
        {
            "reference": str(row[0]),
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


def make_search_module_executor(classroom_id: int, top_k: int):
    def executor(query: str) -> list[dict]:
        return search_similar_chunks_cached(classroom_id, query, top_k)

    return executor
