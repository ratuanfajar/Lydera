from annotation import config, llm

MAX_TOKENS = 3072

SYSTEM = """# Peran
Anda validator independen untuk soal matematika SMA.

# Aturan
Anda TIDAK diberi tahu jawaban yang sudah dianggap benar -- kerjakan soal ini dari nol memakai
HANYA materi sumber yang diberikan sebagai dasar pengetahuan.

# Output
Keluarkan HANYA JSON, tanpa markdown, dengan format:
{"correct_option": "A", "langkah": ["langkah 1", "langkah 2"]}"""


def build_prompt(segment, question_text: str, options: dict, stimulus_text: str = "") -> str:
    opsi_text = "\n".join(f"{label}. {text}" for label, text in options.items())
    parts = [f"Materi sumber:\n{segment.text}"]
    if stimulus_text:
        parts.append(f"Stimulus soal:\n{stimulus_text}")
    parts.append(f"Soal:\n{question_text}\n\n{opsi_text}")
    parts.append("Kerjakan soal ini dari nol berdasarkan materi sumber di atas.")
    return "\n\n".join(parts)


def validate_soal(segment, question_text: str, options: dict, correct_option: str, stimulus_text: str = "") -> dict:
    """Chain 4: re-derive jawaban independen dari sumber yang sama, bandingkan ke hasil Generation."""
    prompt = build_prompt(segment, question_text, options, stimulus_text)
    derived = llm.complete_json(SYSTEM, prompt, model=config.QUIZ_VALIDATOR_MODEL, max_tokens=MAX_TOKENS,
                                 required_keys=["correct_option"])
    return {
        "matches": derived.get("correct_option") == correct_option,
        "derived_option": derived.get("correct_option"),
        "derived_langkah": derived.get("langkah", []),
    }
