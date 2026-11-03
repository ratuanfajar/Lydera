from quizzer import config, prompts
from common import llm

REVISE_SOAL_MAX_TOKENS = 3072
REVISE_STIMULUS_MAX_TOKENS = 1536
REVISE_TYPED_STIMULUS_MAX_TOKENS = 10240
RECHECK_SOAL_MAX_TOKENS = 3072


def revise_soal(source_text, stimulus_text: str, soal: dict, feedback: str) -> dict:
    """Chain 3.5a: edit satu soal yang dikritik guru, dengan konteks soal+stimulus lama sebagai
    anchor. Melaporkan balik lewat `needs_stimulus_change` kalau
    perbaikannya sebenarnya perlu sampai ke stimulus (shared ke soal lain)."""
    prompt = prompts.revise_soal_input(source_text, stimulus_text, soal, feedback)
    return llm.complete_json(
        prompts.REVISE_SOAL_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=REVISE_SOAL_MAX_TOKENS,
        required_keys=["needs_stimulus_change", "question_text", "options", "correct_option", "langkah", "kesimpulan"],
        latex=True,
    )


def revise_stimulus(source_text, stimulus_text: str, feedback: str) -> str:
    """Chain 3.5b: edit stimulus yang sudah ada seminimal mungkin sesuai feedback."""
    prompt = prompts.revise_stimulus_input(source_text, stimulus_text, feedback)
    data = llm.complete_json(
        prompts.REVISE_STIMULUS_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=REVISE_STIMULUS_MAX_TOKENS,
        required_keys=["readable_text"], latex=True,
    )
    return data["readable_text"]


def revise_stimulus_typed(source_text, stimulus_text: str, jenis: str, spec: dict, feedback: str) -> dict:
    """Chain 3.5b untuk stimulus bertipe: edit narasi dan spesifikasi; jenis tidak boleh berubah."""
    prompt = prompts.revise_stimulus_typed_input(source_text, stimulus_text, jenis, spec, feedback)
    data = llm.complete_json(
        prompts.REVISE_STIMULUS_TYPED_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=REVISE_TYPED_STIMULUS_MAX_TOKENS,
        required_keys=["spesifikasi"], latex=True,
    )
    return {"jenis": jenis, "narasi": data.get("narasi") or "", "spesifikasi": data["spesifikasi"]}


def recheck_soal_for_new_stimulus(source_text, new_stimulus_text: str, soal: dict) -> dict:
    """Chain 3.5c: setelah stimulus berubah, periksa satu soal (bisa yang dikritik ATAU soal lain
    di cluster yang sama) masih konsisten."""
    prompt = prompts.recheck_soal_input(source_text, new_stimulus_text, soal)
    return llm.complete_json(
        prompts.RECHECK_SOAL_SYSTEM, prompt, model=config.QUIZ_MODEL, max_tokens=RECHECK_SOAL_MAX_TOKENS,
        required_keys=["question_text", "options", "correct_option", "langkah", "kesimpulan"], latex=True,
    )
