"""Scope gate: cegah pertanyaan yang benar-benar di luar topik (mis. "BPUPKI kapan bubar" saat
belajar Kalkulus) tanpa menolak pertanyaan pengembangan/aplikasi yang masih satu domain mata
pelajaran (mis. "turunan dipakai buat hitung kecepatan mobil gimana?").

Beda dari desain awal (anchor topik statis per-chapter): sekarang scope dinilai dari SKOR
SIMILARITY hasil retrieval pgvector itu sendiri (top-1 dari `search_module`, lintas semua chapter
published di classroom) -- lebih akurat karena dibandingkan ke isi materi yang sebenarnya, bukan
deskripsi ringkas statis, dan otomatis ikut multi-chapter tanpa perlu digabung manual.

2 lapis:
1. Threshold similarity (murah, hampir gratis, reuse hasil retrieval yang memang sudah dipanggil) --
   mayoritas kasus jelas (sangat dekat / sangat jauh) selesai di sini tanpa panggil LLM.
2. LLM classifier (structured output) -- HANYA untuk kasus di antara HIGH/LOW threshold, jumlahnya
   kecil jadi biaya tambahan minimal. Konteks yang dikasih ke classifier adalah CHUNK PALING MIRIP
   yang benar-benar ketemu (heading + potongan isi), bukan anchor statis.

Ini harus jadi langkah PERTAMA sebelum tool calling lain -- keputusan scope tidak boleh bergantung
pada kepatuhan model terhadap instruksi prompt (soft constraint, gampang di-bypass).
"""

from __future__ import annotations

import config
import jsonutil
import llm as annotation_llm

CLASSIFIER_SYSTEM = (
    "Anda menentukan apakah pertanyaan siswa masih relevan dengan materi yang tersedia di kelasnya. "
    "Ada 3 kelas:\n"
    "- inti: langsung tentang isi materi yang diberikan\n"
    "- perluasan: bukan isi materi persis, tapi masih penerapan/pengembangan/konteks dari domain "
    "mata pelajaran yang sama -- termasuk asal-usul atau sejarah singkat suatu KONSEP matematika "
    "(mis. 'siapa yang mencetuskan konsep aritmetika/kalkulus', 'dari mana asal notasi ini')\n"
    "- di_luar_topik: mata pelajaran/domain yang sama sekali berbeda, ATAU pertanyaan yang sudah "
    "melenceng dari konsep ke BIOGRAFI PRIBADI seorang tokoh (kisah hidup, tanggal lahir, "
    "riwayat karier/keluarganya) walau tokoh itu terkait matematika -- itu sudah jadi topik "
    "sejarah/biografi, bukan lagi tentang konsep matematikanya\n\n"
    'Keluarkan HANYA JSON: {"klass": "inti"|"perluasan"|"di_luar_topik", "alasan": "..."}'
)


def check_scope(question: str, top_chunks: list[dict]) -> dict:
    """`top_chunks`: hasil `search_module_executor(question)` (sudah terurut similarity desc).
    Balikkan {"klass": "inti"|"perluasan"|"di_luar_topik", "alasan": str, "similarity": float}."""
    similarity = top_chunks[0]["similarity"] if top_chunks else 0.0

    if similarity >= config.SCOPE_SIM_HIGH:
        return {"klass": "inti", "alasan": "Similarity tinggi terhadap materi yang tersedia.", "similarity": similarity}
    if similarity <= config.SCOPE_SIM_LOW or not top_chunks:
        return {"klass": "di_luar_topik", "alasan": "Tidak ada materi yang cukup mirip.", "similarity": similarity}

    # Zona abu-abu -- serahkan ke LLM classifier, pakai chunk paling mirip sebagai konteks nyata
    # (bukan anchor statis) supaya keputusannya berdasar isi materi yang sebenarnya ada.
    best = top_chunks[0]
    context = f"{best['heading']}: {best['text'][:500]}"
    prompt = f"Materi paling relevan yang tersedia: {context}\n\nPertanyaan siswa: {question}"
    raw = annotation_llm.complete_text(CLASSIFIER_SYSTEM, prompt, model=config.CHAT_MODEL, max_tokens=200)
    try:
        result = jsonutil.parse_json(raw)
    except Exception:
        # Gagal parse -- fail-safe ke "perluasan" (biarkan lanjut, bukan blokir siswa gara-gara
        # error teknis di sisi kita), tapi similarity tetap dicatat untuk audit.
        result = {"klass": "perluasan", "alasan": "Fallback: classifier gagal di-parse."}
    result["similarity"] = similarity
    return result
