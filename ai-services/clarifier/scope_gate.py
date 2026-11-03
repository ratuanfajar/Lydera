from __future__ import annotations

import re

from clarifier import config
from common import jsonutil
from common import guardrails
from common import llm
from common.prompt_format import build_prompt

CLASSIFIER_SYSTEM = build_prompt(
    role="Anda penyaring cakupan untuk asisten belajar matematika siswa tunanetra.",
    task="Tentukan apakah pertanyaan siswa masih relevan dengan materi yang tersedia di kelasnya, lalu pilih satu kelas.",
    context=[
        "inti: langsung tentang isi materi yang diberikan.",
        "perluasan: bukan isi materi persis, tetapi masih penerapan, pengembangan, atau konteks dari domain mata pelajaran yang sama, termasuk asal-usul atau sejarah singkat suatu konsep matematika.",
        "campuran: pertanyaan berisi beberapa sub-pertanyaan yang digabung dalam satu kalimat; sebagian tentang materi atau domain mata pelajaran ini, sebagian lagi domain lain sama sekali (misalnya pemrograman atau mata pelajaran lain).",
        "di_luar_topik: seluruh pertanyaan domain lain tanpa bagian yang nyambung, atau sudah melenceng ke biografi pribadi seorang tokoh (kisah hidup, tanggal lahir, karier) walau tokoh itu terkait matematika.",
    ],
    rules=[
        "Tulis alasan singkat lebih dulu, baru pilih kelas, supaya pilihan mengikuti alasan.",
        "Isi bagian_di_luar_topik hanya bila kelasnya campuran, berupa ringkasan singkat bagian yang di luar topik; selain itu kosongkan.",
    ],
    output_format='JSON: {"alasan": "...", "klass": "inti"|"perluasan"|"campuran"|"di_luar_topik", "bagian_di_luar_topik": "..."}',
    examples="""Materi:
<teks_modul>
sudut pusat dan sudut keliling lingkaran.
</teks_modul>
Pertanyaan:
<pertanyaan_siswa>
Berapa besar sudut keliling bila sudut pusatnya 80 derajat?
</pertanyaan_siswa>
{"alasan": "Langsung menerapkan hubungan sudut pusat dan sudut keliling.", "klass": "inti", "bagian_di_luar_topik": ""}

Materi:
<teks_modul>
sudut pusat dan sudut keliling lingkaran.
</teks_modul>
Pertanyaan:
<pertanyaan_siswa>
Di kehidupan sehari-hari, lingkaran dipakai untuk apa saja?
</pertanyaan_siswa>
{"alasan": "Bukan isi materi persis, tetapi penerapan konsep lingkaran.", "klass": "perluasan", "bagian_di_luar_topik": ""}

Materi:
<teks_modul>
sudut pusat dan sudut keliling lingkaran.
</teks_modul>
Pertanyaan:
<pertanyaan_siswa>
Jelaskan sudut keliling dan buatkan programnya dalam Python.
</pertanyaan_siswa>
{"alasan": "Bagian sudut keliling sesuai materi, bagian pemrograman domain lain.", "klass": "campuran", "bagian_di_luar_topik": "membuat program Python"}

Materi:
<teks_modul>
sudut pusat dan sudut keliling lingkaran.
</teks_modul>
Pertanyaan:
<pertanyaan_siswa>
Resep nasi goreng yang enak bagaimana?
</pertanyaan_siswa>
{"alasan": "Tidak ada hubungannya dengan matematika.", "klass": "di_luar_topik", "bagian_di_luar_topik": ""}""",
)

_COMPOUND_MARKERS = re.compile(
    r"\?.+\?|\bdan (?:juga |bagaimana|apa|kenapa|mengapa|gimana)\b|\bserta\b|\blalu bagaimana\b",
    re.IGNORECASE,
)


def _looks_compound(question: str) -> bool:
    return bool(_COMPOUND_MARKERS.search(question))


def check_scope(question: str, top_chunks: list[dict]) -> dict:
    """`top_chunks`: hasil `search_module_executor(question)` (urutan fusi, bukan similarity).
    Balikkan {"klass": "inti"|"perluasan"|"campuran"|"di_luar_topik", "alasan": str,
    "bagian_di_luar_topik": str | None, "similarity": float}."""
    best = max(top_chunks, key=lambda chunk: chunk["similarity"]) if top_chunks else None
    similarity = best["similarity"] if best else 0.0
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
    context =f"{best['heading']}: {best['text'][:500]}"
    prompt = f"Materi:\n{guardrails.wrap('teks_modul', context)}\nPertanyaan:\n{guardrails.wrap('pertanyaan_siswa', question)}"
    try:
        raw = llm.complete_text(CLASSIFIER_SYSTEM, prompt, model=config.CHAT_MODEL, max_tokens=250)
    except llm.ContentFilterError:
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
