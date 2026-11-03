import re
from typing import Callable

from clarifier import config, retrieval_grader

OPTION_LABELS = ("A", "B", "C", "D")
CHOICE = re.compile(r"^\s*(?:jawaban(?:ku)?|opsi|pilihan)?\s*[:\-]?\s*([a-d])\s*[.!]?\s*$", re.IGNORECASE)


def parse_choice(text: str) -> str | None:
    match = CHOICE.match(text)
    return match.group(1).upper() if match else None


def select_source(topic: str, search_module_executor: Callable[[str], list[dict]]) -> dict | None:
    """Teks sumber dari bagian modul yang relevan dengan topik; None bila tidak ada yang relevan."""
    chunks = retrieval_grader.safe_chunks(search_module_executor(topic))
    relevant = retrieval_grader.filter_chunks(chunks, retrieval_grader.grade_chunks(topic, chunks))[: config.PRACTICE_MAX_CHUNKS]
    text = "\n\n".join(chunk["text"] for chunk in relevant)[: config.PRACTICE_SOURCE_MAX_CHARS]
    if not text.strip():
        return None
    return {"text": text, "headings": list(dict.fromkeys(chunk["heading"] for chunk in relevant if chunk.get("heading")))}


def stored_form(soal: dict, headings: list[str]) -> dict:
    keys = ("question_text", "options", "correct_option", "langkah", "kesimpulan", "markup", "stimulus", "bloom_level")
    return {**{key: soal.get(key) for key in keys}, "headings": headings}


def reply(message: str, markup: str | None = None, latihan: dict | None = None) -> dict:
    return {
        "status": "answered", "message": message, "message_markup": markup, "rumus": [], "tabel": None, "tabel_bacaan": None,
        "tabel_ringkasan": None, "format_issues": [], "sources": [], "suggested_questions": None, "tool_calls": [],
        "scope": {"klass": "inti", "similarity": None}, "latihan": latihan,
    }


def declined_reply(message: str) -> dict:
    return reply(message, latihan={"tahap": "ditolak"})


def question_reply(stored: dict) -> dict:
    markup, stimulus = stored.get("markup"), stored.get("stimulus")
    options = stored["options"]
    readable = _question_text(stored, stored["question_text"], options, stimulus and stimulus["readable_text"])
    shown_stimulus = stimulus and (stimulus.get("source_markup") or stimulus["readable_text"])
    has_markup = bool(markup) or bool(stimulus and stimulus.get("source_markup"))
    display = _question_text(stored, markup["question"] if markup else stored["question_text"], markup["options"] if markup else options, shown_stimulus) if has_markup else None
    return reply(readable, display, {"tahap": "soal", "pilihan": list(OPTION_LABELS)})


def answer_reply(stored: dict, chosen: str) -> dict:
    correct, markup = stored["correct_option"], stored.get("markup")
    verdict = "Jawabanmu benar." if chosen == correct else "Jawabanmu salah."
    readable = _result_text(verdict, correct, stored["options"][correct], stored["langkah"], stored["kesimpulan"])
    display = _result_text(verdict, correct, markup["options"][correct], markup["langkah"], markup["kesimpulan"]) if markup else None
    return reply(readable, display, {"tahap": "hasil", "benar": chosen == correct})


def _question_text(stored: dict, question: str, options: dict, stimulus: str | None) -> str:
    lines = [config.PRACTICE_LABEL, f"Tingkat {stored['bloom_level']} dari 3."]
    if stimulus:
        lines.append(stimulus.strip())
    lines.append(f"Soal: {question}")
    lines += [f"Pilihan {label}: {options[label]}" for label in OPTION_LABELS]
    lines.append("Ketik huruf pilihanmu: A, B, C, atau D.")
    return "\n".join(lines)


def _result_text(verdict: str, correct: str, correct_text: str, steps: list[str], conclusion: str) -> str:
    lines = [f"{verdict} Jawaban yang benar opsi {correct}, yaitu {correct_text.strip().rstrip('.')}.", "Penyelesaiannya:"]
    lines += [f"Langkah {number}. {step}" for number, step in enumerate(steps, start=1)]
    lines += [f"Kesimpulan: {conclusion}", config.PRACTICE_LABEL]
    return "\n".join(lines)
