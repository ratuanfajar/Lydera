import re

from common.notation_check import has_raw_notation
from evaluaizer import config

META_PHRASES = re.compile(r"tidak (disertakan|menulis langkah|ada catatan|ada langkah)|catatan (langkah|pengerjaan)|langkah tertulis|langkah kunci|kunci jawaban|materi sumber", re.IGNORECASE)
RAW_QUANTITY = re.compile(r"\d[A-Za-z]\b")
FOREIGN_SCRIPT = re.compile("[Ͱ-῿⺀-￿]")
MARKDOWN = re.compile(r"[*#`|]|^\s*[-•]\s", re.MULTILINE)


def result_issues(result: dict, student_steps: int, key_steps: int) -> list[str]:
    issues = _field_issues(result, student_steps)
    points = result.get("justification_points")
    if not isinstance(points, list) or not config.MIN_POINTS <= len(points) <= config.MAX_POINTS:
        return issues + [f"justification_points harus berisi {config.MIN_POINTS} sampai {config.MAX_POINTS} poin."]
    texts = [str(result.get("diagnosis") or "")]
    for number, point in enumerate(points, start=1):
        issues.extend(_point_issues(number, point, key_steps))
        texts.append(str(point.get("point", "")) if isinstance(point, dict) else "")
    issues.extend(_text_issues(texts))
    marked = sum(1 for point in points if isinstance(point, dict) and point.get("is_divergence") is True)
    if marked > 1:
        issues.append("Hanya satu poin boleh bernilai is_divergence true.")
    if result.get("divergence_step") is not None and marked != 1:
        issues.append("Ada divergence_step: tepat satu poin harus bernilai is_divergence true.")
    return issues


def _field_issues(result: dict, student_steps: int) -> list[str]:
    issues = []
    kind, step = result.get("error_type"), result.get("divergence_step")
    if kind not in config.ERROR_TYPES:
        issues.append(f"error_type harus salah satu dari {', '.join(config.ERROR_TYPES)}.")
    if not str(result.get("diagnosis") or "").strip():
        issues.append("diagnosis tidak boleh kosong.")
    if step is not None and (isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= student_steps):
        issues.append(f"divergence_step harus null atau nomor langkah siswa antara 1 dan {student_steps}.")
    if student_steps == 0 and (step is not None or kind != "tanpa_langkah"):
        issues.append("Siswa tidak menulis langkah: divergence_step harus null dan error_type 'tanpa_langkah'.")
    if student_steps > 0 and kind == "tanpa_langkah":
        issues.append("Siswa menulis langkah: error_type tidak boleh 'tanpa_langkah'.")
    return issues


def _point_issues(number: int, point, key_steps: int) -> list[str]:
    if not isinstance(point, dict) or not str(point.get("point") or "").strip():
        return [f"Poin {number} harus berupa objek dengan teks 'point' tidak kosong."]
    issues = []
    if "is_divergence" in point and not isinstance(point["is_divergence"], bool):
        issues.append(f"Poin {number}: is_divergence harus true atau false.")
    ref = point.get("step_ref")
    if ref is not None and (isinstance(ref, bool) or not isinstance(ref, int) or not 1 <= ref <= key_steps):
        issues.append(f"Poin {number}: step_ref harus null atau nomor langkah kunci antara 1 dan {key_steps}.")
    if len(str(point["point"])) > config.MAX_POINT_CHARS:
        issues.append(f"Poin {number} terlalu panjang; cukup satu sampai dua kalimat.")
    return issues


def _text_issues(texts: list[str]) -> list[str]:
    issues = []
    if any(has_raw_notation(text) or RAW_QUANTITY.search(text) for text in texts):
        issues.append("Teks memakai simbol atau rumus mentah; tulis dengan kata agar terbaca pembaca layar.")
    if any(FOREIGN_SCRIPT.search(text) for text in texts):
        issues.append("Teks memuat huruf atau kata bukan Bahasa Indonesia; tulis seluruhnya dalam Bahasa Indonesia.")
    if any(MARKDOWN.search(text) for text in texts):
        issues.append("Teks memakai markdown atau butir; tulis kalimat biasa.")
    if any(META_PHRASES.search(text) for text in texts):
        issues.append("Teks memuat kalimat meta tentang catatan atau langkah siswa; jelaskan langsung isi pelajarannya.")
    return issues
