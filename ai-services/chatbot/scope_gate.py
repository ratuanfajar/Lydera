"""Scope gate: cegah pertanyaan yang benar-benar di luar topik (mis. "BPUPKI kapan bubar" saat
belajar Kalkulus) tanpa menolak pertanyaan pengembangan/aplikasi yang masih satu domain mata
pelajaran (mis. "turunan dipakai buat hitung kecepatan mobil gimana?").

Beda dari desain awal (anchor topik statis per-chapter): sekarang scope dinilai dari SKOR
SIMILARITY hasil retrieval pgvector itu sendiri (top-1 dari `search_module`, lintas semua chapter
published di classroom) -- lebih akurat karena dibandingkan ke isi materi yang sebenarnya, bukan
deskripsi ringkas statis, dan otomatis ikut multi-chapter tanpa perlu digabung manual.

4 kelas (bukan 3) -- dipisah biar pertanyaan MAJEMUK bisa dijawab ADAPTIF, bukan ditolak mentah:
- inti: langsung tentang isi materi
- perluasan: pengembangan/konteks dari domain yang sama (masih dijawab penuh)
- campuran: pertanyaan berisi beberapa sub-pertanyaan, SEBAGIAN nyambung ke materi, SEBAGIAN lagi
  domain lain sama sekali -- tetap DIPROSES (bukan ditolak), tapi agent (lihat agent.py) cuma
  menjawab bagian yang nyambung, menyatakan eksplisit bagian lain di luar cakupan, dan kasih
  pertanyaan rujukan supaya siswa tahu apa yang masih bisa ditanyakan.
- di_luar_topik: SELURUH pertanyaan tidak ada satupun bagian yang nyambung -- baru ini yang
  benar-benar ditolak tanpa tool calling sama sekali.

2 lapis:
1. Threshold similarity (murah, hampir gratis, reuse hasil retrieval yang memang sudah dipanggil) --
   mayoritas kasus jelas (sangat dekat / sangat jauh) selesai di sini tanpa panggil LLM. TIDAK
   dipakai kalau pertanyaan kelihatan majemuk (lihat `_looks_compound`) -- similarity gabungan bisa
   tinggi walau cuma separuh yang relevan, jadi wajib diserahkan ke classifier supaya per-bagian
   dinilai, bukan digabung jadi satu angka.
2. LLM classifier (structured output) -- zona abu-abu ATAU pertanyaan majemuk. Konteks yang dikasih
   adalah CHUNK PALING MIRIP yang benar-benar ketemu (heading + potongan isi), bukan anchor statis.

Ini harus jadi langkah PERTAMA sebelum tool calling lain -- keputusan scope tidak boleh bergantung
pada kepatuhan model terhadap instruksi prompt (soft constraint, gampang di-bypass).
"""

from __future__ import annotations

import re

import config
import jsonutil
import llm as annotation_llm

CLASSIFIER_SYSTEM = (
    "Anda menentukan apakah pertanyaan siswa masih relevan dengan materi yang tersedia di kelasnya. "
    "Ada 4 kelas:\n"
    "- inti: langsung tentang isi materi yang diberikan\n"
    "- perluasan: bukan isi materi persis, tapi masih penerapan/pengembangan/konteks dari domain "
    "mata pelajaran yang sama -- termasuk asal-usul atau sejarah singkat suatu KONSEP matematika\n"
    "- campuran: pertanyaan berisi BEBERAPA sub-pertanyaan digabung jadi satu kalimat -- SEBAGIAN "
    "tentang materi/domain mata pelajaran ini, SEBAGIAN LAGI domain lain sama sekali (mis. "
    "pemrograman/coding, mata pelajaran lain). Kalau begini, isi juga field \"bagian_di_luar_topik\" "
    "berisi ringkasan singkat bagian mana yang di luar topik itu.\n"
    "- di_luar_topik: SELURUH pertanyaan domain lain (tidak ada bagian yang nyambung sama sekali), "
    "ATAU sudah melenceng ke BIOGRAFI PRIBADI seorang tokoh (kisah hidup, tanggal lahir, karier) "
    "walau tokoh itu terkait matematika\n\n"
    'Keluarkan HANYA JSON: {"klass": "inti"|"perluasan"|"campuran"|"di_luar_topik", "alasan": "...", '
    '"bagian_di_luar_topik": "..." (isi cuma kalau klass campuran, kosongkan kalau tidak)}'
)

# Heuristik murah: pertanyaan yang gabung beberapa klausa (konjungsi/tanda tanya ganda) berpotensi
# majemuk -- bukan deteksi sempurna, cuma pemicu supaya jalur cepat similarity-tinggi tidak dipakai
# untuk kasus ini, dipaksa lewat LLM classifier yang bisa menilai tiap bagian secara terpisah.
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
    # sebagai konteks nyata (bukan anchor statis) supaya keputusannya berdasar isi materi yang
    # sebenarnya ada.
    best = top_chunks[0]
    context = f"{best['heading']}: {best['text'][:500]}"
    prompt = f"Materi paling relevan yang tersedia: {context}\n\nPertanyaan siswa: {question}"
    raw = annotation_llm.complete_text(CLASSIFIER_SYSTEM, prompt, model=config.CHAT_MODEL, max_tokens=250)
    try:
        result = jsonutil.parse_json(raw)
    except Exception:
        # Gagal parse -- fail-safe ke "perluasan" (biarkan lanjut, bukan blokir siswa gara-gara
        # error teknis di sisi kita), tapi similarity tetap dicatat untuk audit.
        result = {"klass": "perluasan", "alasan": "Fallback: classifier gagal di-parse.", "bagian_di_luar_topik": None}
    result.setdefault("bagian_di_luar_topik", None)
    result["similarity"] = similarity
    return result
