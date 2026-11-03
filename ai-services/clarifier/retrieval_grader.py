from __future__ import annotations

import json

from clarifier import config
from common import guardrails
from common import llm
from common.prompt_format import build_prompt

GRADER_SYSTEM = build_prompt(
    role="Anda penilai relevansi hasil pencarian modul untuk asisten belajar matematika.",
    task=(
        "Nilai apakah tiap hasil pencarian modul benar-benar relevan untuk menjawab pertanyaan siswa, "
        "berdasarkan konsep atau metode yang dibahas, bukan kemiripan kata atau angka."
    ),
    context=[
        "Tiap hasil ditandai nomor referensi dalam kurung siku, misalnya [241]. Nomor itu yang dipakai di relevant_references, bukan judul atau isinya.",
        "correct: ada hasil yang relevan dan cukup untuk menjawab.",
        "ambiguous: ada yang relevan tetapi belum lengkap atau meyakinkan untuk menjawab penuh.",
        "incorrect: tidak ada satu pun hasil yang relevan.",
    ],
    rules=[
        "Hasil yang kebetulan memuat angka atau istilah yang sama dengan pertanyaan tetapi konsepnya berbeda tetap tidak relevan.",
        "Tulis alasan singkat lebih dulu (konsep pertanyaan, konsep tiap hasil, lalu kecocokannya), baru tentukan verdict dan referensinya.",
    ],
    output_format='JSON: {"alasan": "...", "verdict": "correct"|"ambiguous"|"incorrect", "relevant_references": ["241", "227"]}',
    examples="""Pertanyaan siswa:
<pertanyaan_siswa>
Bagaimana mencari fungsi invers?
</pertanyaan_siswa>

Hasil pencarian modul:
<teks_modul>
[241] Fungsi invers: cara mencari fungsi invers adalah menukar x dan y lalu menyelesaikan untuk x.

[227] Grafik relasi: titik puncak grafik berada di x sama dengan 2.
</teks_modul>
{"alasan": "Pertanyaan tentang metode invers. Hasil 241 membahas metode itu; hasil 227 membahas grafik relasi, konsepnya berbeda.", "verdict": "correct", "relevant_references": ["241"]}

Pertanyaan siswa:
<pertanyaan_siswa>
Apa itu peluang kejadian majemuk?
</pertanyaan_siswa>

Hasil pencarian modul:
<teks_modul>
[310] Statistika: rata-rata adalah jumlah data dibagi banyak data.
</teks_modul>
{"alasan": "Pertanyaan tentang peluang, hasil hanya membahas rata-rata.", "verdict": "incorrect", "relevant_references": []}""",
)

NOTE_INCORRECT = (
    "Tidak ada hasil modul yang dinilai relevan untuk pertanyaan ini. Coba search_oer."
)
NOTE_AMBIGUOUS = (
    "Hasil modul relevan tapi belum lengkap/meyakinkan. Pertimbangkan melengkapi dengan search_oer "
    "sebelum compose_answer."
)


def grade_chunks(question: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {"verdict": "incorrect", "relevant_references": []}
    listing = "\n\n".join(f"[{c['reference']}] {c['heading']}: {c['text'][:400]}" for c in chunks)
    prompt = f"Pertanyaan siswa:\n{guardrails.wrap('pertanyaan_siswa', question)}\n\nHasil pencarian modul:\n{guardrails.wrap('teks_modul', listing)}"
    try:
        result = llm.complete_json(GRADER_SYSTEM, prompt, model=config.CHAT_MODEL, max_tokens=500,
                                    required_keys=["verdict", "relevant_references"])
    except Exception:
        return {"verdict": "ambiguous", "relevant_references": [c["reference"] for c in chunks]}
    if result.get("verdict") not in ("correct", "ambiguous", "incorrect"):
        result["verdict"] = "ambiguous"
    return result


def filter_chunks(chunks: list[dict], graded: dict) -> list[dict]:
    keep = {str(r) for r in (graded.get("relevant_references") or [])}
    return [c for c in chunks if str(c["reference"]) in keep]


def safe_chunks(chunks: list[dict]) -> list[dict]:
    return [chunk for chunk in chunks if not guardrails.injection_markers(chunk.get("text", ""), strict=False)]


def evaluate(question: str, chunks: list[dict]) -> tuple[list[dict], str]:
    """Return (chunk_relevan, result_text_untuk_pesan_tool)."""
    chunks = safe_chunks(chunks)
    graded = grade_chunks(question, chunks)
    relevant = filter_chunks(chunks, graded)
    payload = {"chunks": relevant, "verdict": graded["verdict"]}
    if graded["verdict"] == "incorrect":
        payload["catatan"] = NOTE_INCORRECT
    elif graded["verdict"] == "ambiguous":
        payload["catatan"] = NOTE_AMBIGUOUS
    return relevant, json.dumps(payload, ensure_ascii=False)
