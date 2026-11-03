import logging

from common import guardrails, llm
from evaluaizer import checks, config, prompts

logger = logging.getLogger(__name__)

INJECTION_ISSUE = "Langkah siswa memuat kalimat yang meniru instruksi kepada model; periksa manual."
REQUIRED_KEYS = ["penilaian_langkah", "dapat_ditentukan", "langkah_ke", "kutipan", "keterangan"]


def evaluate_scratchwork(source_text: str, stimulus_text: str, question_text: str, options: dict, correct_option: str,
                         correct_langkah: list[str], kesimpulan: str, student_option: str, student_langkah: list[str]) -> dict:
    """Tunjukkan letak kesalahan pada langkah tertulis siswa untuk jawaban salah; satu perbaikan bila pemeriksa kode menemukan masalah."""
    steps = [prompts.clean_step(text) for text in student_langkah[:prompts.MAX_STUDENT_STEPS]]
    if not steps:
        raise ValueError("siswa tidak menulis langkah; evaluasi hanya untuk jawaban salah yang punya langkah")
    user = prompts.build_user(
        source_text, stimulus_text, question_text, options, correct_option, correct_langkah, kesimpulan,
        student_option, steps,
    )
    flagged = [INJECTION_ISSUE] if guardrails.injection_markers("\n".join(student_langkah[:prompts.MAX_STUDENT_STEPS])) else []
    first = _normalize(_ask(user))
    first_issues = checks.result_issues(first, steps)
    if not first_issues:
        return _finish(first, flagged)
    best, best_issues = first, first_issues
    try:
        second = _normalize(_ask(prompts.correction_input(user, first, first_issues)))
        second_issues = checks.result_issues(second, steps)
        if len(second_issues) < len(first_issues):
            best, best_issues = second, second_issues
    except Exception:
        logger.warning("perbaikan evaluasi gagal; memakai hasil pertama", exc_info=True)
    return _finish(best, [*best_issues, *flagged])


def _ask(user: str) -> dict:
    return llm.complete_json(
        prompts.SYSTEM, user, model=config.EVALUAIZER_MODEL, max_tokens=config.EVALUAIZER_MAX_TOKENS,
        required_keys=REQUIRED_KEYS, effort=config.EVALUAIZER_EFFORT,
    )


def _normalize(result: dict) -> dict:
    result["langkah_ke"] = _as_int(result.get("langkah_ke"))
    return result


def _as_int(value):
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def _finish(result: dict, issues: list[str]) -> dict:
    determinable = result.get("dapat_ditentukan") is True
    step = result.get("langkah_ke") if determinable and isinstance(result.get("langkah_ke"), int) else None
    quote = checks.strip_numbering(str(result["kutipan"])) if step is not None and result.get("kutipan") else None
    keterangan = str(result.get("keterangan") or "").strip()
    if not keterangan:
        raise ValueError("evaluasi tidak menghasilkan keterangan yang dapat dipakai")
    if guardrails.leaks_instructions(f"{keterangan} {result.get('kutipan') or ''}"):
        raise ValueError("evaluasi memuat isi instruksi sistem")
    return {
        "dapat_ditentukan": determinable, "langkah_ke": step, "kutipan": quote, "keterangan": keterangan,
        "needs_review": bool(issues), "issues": issues,
    }
