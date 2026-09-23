from __future__ import annotations

import re

from annotation import config
from quiz import jsonutil
from annotation import llm as annotation_llm

CLASSIFIER_SYSTEM = (
    "Anda menentukan apakah pertanyaan siswa masih relevan dengan materi yang tersedia di kelasnya.\n\n"
    "# Kelas\n"
    "- inti: langsung tentang isi materi yang diberikan\n"
    "- perluasan: bukan isi materi persis, tapi masih penerapan/pengembangan/konteks dari domain "
    "mata pelajaran yang sama -- termasuk asal-usul atau sejarah singkat suatu KONSEP matematika\n"
    "- campuran: pertanyaan berisi BEBERAPA sub-pertanyaan digabung jadi satu kalimat -- SEBAGIAN "
    "tentang materi/domain mata pelajaran ini, SEBAGIAN LAGI domain lain sama sekali (mis. "
    "pemrograman/coding, mata pelajaran lain). Isi juga field \"bagian_di_luar_topik\" berisi "
    "ringkasan singkat bagian yang di luar topik.\n"
    "- di_luar_topik: SELURUH pertanyaan domain lain (tidak ada bagian yang nyambung sama sekali), "
    "ATAU sudah melenceng ke BIOGRAFI PRIBADI seorang tokoh (kisah hidup, tanggal lahir, karier) "
    "walau tokoh itu terkait matematika\n\n"
    "# Output\n"
    'JSON: {"klass": "inti"|"perluasan"|"campuran"|"di_luar_topik", "alasan": "...", '
    '"bagian_di_luar_topik": "..." (isi cuma kalau klass campuran, kosongkan kalau tidak)}'
)

_COMPOUND_MARKERS = re.compile(
    r"\?.+\?|\bdan (?:juga |bagaimana|apa|kenapa|mengapa|gimana)\b|\bserta\b|\blalu bagaimana\b",
    re.IGNORECASE,
)


def _looks_compound(question: str) -> bool:
    return bool(_COMPOUND_MARKERS.search(question))


def check_scope(question: str, top_chunks: list[dict]) -> dict:
    """`top_chunks`: hasil `search_module_executor(question)` (sudah terurut similarity desc).
    Balikkan {"klass": "inti"|"perluasan"|"campuran"|"di_luar_topik", "alasan": str,
    "bagian_di_luar_topik": str | None, "similarity": float}."""
    similarity = top_chunks[0]["similarity"] if top_chunks else 0.0
    compound = _looks_compound(question)

    if similarity >= config.SCOPE_SIM_HIGH and not compound:
        return {
            "klass": "inti",
            "alasan": "Similarity tinggi terhadap materi yang tersedia.",
            "bagian_di_luar_topik": None,
            "similarity": similarity,
        }
    if similarity <= config.SCOPE_SIM_LOW or not top_chunks:
        return {
            "klass": "di_luar_topik",
            "alasan": "Tidak ada materi yang cukup mirip.",
            "bagian_di_luar_topik": None,
            "similarity": similarity,
        }

    # Zona abu-abu ATAU pertanyaan majemuk -- serahkan ke LLM classifier, pakai chunk paling mirip
    best = top_chunks[0]
    context = f"{best['heading']}: {best['text'][:500]}"
    prompt = f"Materi paling relevan yang tersedia: {context}\n\nPertanyaan siswa: {question}"
    try:
        raw = annotation_llm.complete_text(CLASSIFIER_SYSTEM, prompt, model=config.CHAT_MODEL, max_tokens=250)
    except annotation_llm.ContentFilterError:
        return {
            "klass": "di_luar_topik",
            "alasan": "Pertanyaan ditolak filter keamanan (terindikasi upaya memanipulasi instruksi sistem).",
            "bagian_di_luar_topik": None,
            "similarity": similarity,
        }
    try:
        result = jsonutil.parse_json(raw)
    except Exception:
        result = {"klass": "perluasan", "alasan": "Fallback: classifier gagal di-parse.", "bagian_di_luar_topik": None}
    result.setdefault("bagian_di_luar_topik", None)
    result["similarity"] = similarity
    return result
