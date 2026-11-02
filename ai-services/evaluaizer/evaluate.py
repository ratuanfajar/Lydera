import logging

from common import llm
from evaluaizer import checks, config, prompts

logger = logging.getLogger(__name__)

ORDINALS = ("satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan")
REQUIRED_KEYS = ["divergence_step", "error_type", "diagnosis", "justification_points"]


def evaluate_scratchwork(source_text: str, stimulus_text: str, question_text: str, options: dict, correct_option: str,
                         correct_langkah: list[str], kesimpulan: str, student_option: str, student_langkah: list[str]) -> dict:
    """Jelaskan letak kesalahan siswa pada jawaban salah sebagai poin bernomor; satu perbaikan bila pemeriksa kode menemukan masalah."""
    user = prompts.build_user(
        source_text, stimulus_text, question_text, options, correct_option, correct_langkah, kesimpulan,
        student_option, student_langkah,
    )
    first = _normalize(_ask(user))
    first_issues = _issues(first, student_langkah, correct_langkah)
    if not first_issues:
        return _finish(first, [], len(student_langkah), len(correct_langkah))
    best, best_issues = first, first_issues
    try:
        second = _normalize(_ask(prompts.correction_input(user, first, first_issues)))
        second_issues = _issues(second, student_langkah, correct_langkah)
        if len(second_issues) < len(first_issues):
            best, best_issues = second, second_issues
    except Exception:
        logger.warning("perbaikan evaluasi gagal; memakai hasil pertama", exc_info=True)
    return _finish(best, best_issues, len(student_langkah), len(correct_langkah))


def _ask(user: str) -> dict:
    return llm.complete_json(
        prompts.SYSTEM, user, model=config.EVALUAIZER_MODEL, max_tokens=config.EVALUAIZER_MAX_TOKENS,
        required_keys=REQUIRED_KEYS, effort=config.EVALUAIZER_EFFORT,
    )


def _issues(result: dict, student_langkah: list[str], correct_langkah: list[str]) -> list[str]:
    return checks.result_issues(result, len(student_langkah), len(correct_langkah))


def _normalize(result: dict) -> dict:
    result["divergence_step"] = _as_int(result.get("divergence_step"))
    points = result.get("justification_points")
    if isinstance(points, list):
        for point in points:
            if isinstance(point, dict):
                point["step_ref"] = _as_int(point.get("step_ref"))
    return result


def _as_int(value):
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def _in_range(value, upper: int):
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= upper else None


def _finish(result: dict, issues: list[str], student_steps: int, key_steps: int) -> dict:
    raw_points = result["justification_points"] if isinstance(result.get("justification_points"), list) else []
    points = [
        {
            "point": str(point["point"]).strip(), "step_ref": _in_range(point.get("step_ref"), key_steps),
            "is_divergence": point.get("is_divergence") is True,
        }
        for point in raw_points[:len(ORDINALS)] if isinstance(point, dict) and str(point.get("point") or "").strip()
    ]
    if not points:
        raise ValueError("evaluasi tidak menghasilkan poin penjelasan yang dapat dipakai")
    return {
        "divergence_step": _in_range(result["divergence_step"], student_steps),
        "error_type": result["error_type"] if result["error_type"] in config.ERROR_TYPES else "lainnya",
        "diagnosis": str(result.get("diagnosis") or "").strip(),
        "justification_points": points,
        "personalized_justification": " ".join(
            f"Poin {ORDINALS[number - 1]}. {point['point']}" for number, point in enumerate(points, start=1)
        ),
        "needs_review": bool(issues),
        "issues": issues,
    }
