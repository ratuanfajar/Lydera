from quizzer import config, prompts
from common import llm

LOTS_MAX_TOKENS = 1536
HOTS_MAX_TOKENS = 10240

REQUIRED_KEYS = ["analisis_level", "question_text", "options", "correct_option", "langkah", "kesimpulan", "stimulus"]


def generate_soal(point: dict, source_text: str, bloom_level: int, cp_text: str = "", correction: str = "", visuals: tuple = ()) -> dict:
    """Chain 3: hasilkan satu soal dari satu poin dan teks sumbernya; `visuals` berisi jenis blok gambar atau tabel di sumber."""
    prompt = prompts.generate_input(point, source_text, bloom_level, cp_text, correction, visuals)
    max_tokens = HOTS_MAX_TOKENS if bloom_level >= 4 else LOTS_MAX_TOKENS
    effort = config.HOTS_EFFORT if bloom_level >= 4 else None
    data = llm.complete_json(
        prompts.GENERATE_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=max_tokens, effort=effort,
        required_keys=REQUIRED_KEYS + (["pilihan_stimulus"] if bloom_level >= 4 and prompts.TYPED_ACTIVE else []), latex=True,
    )
    data["bloom_level"] = bloom_level
    data["reading_order_start"] = point["order_start"]
    data["reading_order_end"] = point["order_end"]
    return data
