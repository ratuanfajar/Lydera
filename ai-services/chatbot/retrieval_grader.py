from __future__ import annotations

import json

from annotation import config, llm

GRADER_SYSTEM = (
    "Anda menilai apakah tiap hasil pencarian modul di bawah benar-benar relevan untuk menjawab "
    "pertanyaan siswa -- berdasarkan KONSEP/METODE yang dibahas, bukan cuma kemiripan kata atau "
    "angka. Kalau sebuah hasil kebetulan memuat angka/istilah yang sama dengan pertanyaan tapi "
    "topik/konsepnya BEDA (mis. pertanyaan soal turunan, tapi hasil membahas grafik relasi lain "
    "yang kebetulan titik puncaknya punya angka sama), hasil itu TETAP TIDAK RELEVAN.\n\n"
    "Tiap hasil ditandai NOMOR REFERENSI dalam kurung siku, mis. \"[241] judul: isi...\" -- nomor "
    "241 itu yang dipakai di relevant_references, BUKAN judul atau isinya.\n\n"
    "# Verdict\n"
    "- correct: ada hasil yang relevan dan cukup untuk menjawab\n"
    "- ambiguous: ada yang relevan tapi belum lengkap/meyakinkan untuk menjawab penuh\n"
    "- incorrect: tidak ada satupun hasil yang relevan\n\n"
    "# Output\n"
    'JSON: {"verdict": "correct"|"ambiguous"|"incorrect", "relevant_references": ["241", "227"]}'
)

NOTE_INCORRECT = (
    "Tidak ada hasil modul yang dinilai relevan untuk pertanyaan ini. Coba search_oer atau "
    "search_academic_web."
)
NOTE_AMBIGUOUS = (
    "Hasil modul relevan tapi belum lengkap/meyakinkan. Pertimbangkan melengkapi dengan search_oer "
    "atau search_academic_web sebelum compose_answer."
)


def grade_chunks(question: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {"verdict": "incorrect", "relevant_references": []}
    listing = "\n\n".join(f"[{c['reference']}] {c['heading']}: {c['text'][:400]}" for c in chunks)
    prompt = f"Pertanyaan siswa: {question}\n\nHasil pencarian modul:\n{listing}"
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


def evaluate(question: str, chunks: list[dict]) -> tuple[list[dict], str]:
    """Return (chunk_relevan, result_text_untuk_pesan_tool)."""
    graded = grade_chunks(question, chunks)
    relevant = filter_chunks(chunks, graded)
    payload = {"chunks": relevant, "verdict": graded["verdict"]}
    if graded["verdict"] == "incorrect":
        payload["catatan"] = NOTE_INCORRECT
    elif graded["verdict"] == "ambiguous":
        payload["catatan"] = NOTE_AMBIGUOUS
    return relevant, json.dumps(payload, ensure_ascii=False)
