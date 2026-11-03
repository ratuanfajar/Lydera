import re

from common.notation_check import has_raw_notation
from quizzer import config
from quizzer.stimulus import registry

LABELS = ("A", "B", "C", "D")

def _visual_pattern(words: str) -> re.Pattern:
    return re.compile(
        rf"\b({words})\s+(berikut|di atas|di bawah|tersebut|ini)\b"
        rf"|\b(lihat|perhatikan|amati|tampak pada|terlihat pada|seperti pada)\s+({words})\b",
        re.IGNORECASE,
    )


VISUAL_REFERENCE = _visual_pattern("gambar|grafik|diagram|tabel|ilustrasi|foto|sketsa")
VISUAL_REFERENCE_WITH_TABLE = _visual_pattern("gambar|grafik|diagram|ilustrasi|foto|sketsa")
VISUAL_REFERENCE_TYPED = _visual_pattern("ilustrasi|foto|sketsa")
IMAGE_LOCATION = re.compile(r"\b(pada|dalam|di)\s+gambar\b", re.IGNORECASE)


def _visual_pattern_for(stimulus) -> re.Pattern:
    if registry.is_typed(stimulus):
        return VISUAL_REFERENCE_TYPED
    has_table = isinstance(stimulus, dict) and "<table" in str(stimulus.get("source_markup", ""))
    return VISUAL_REFERENCE_WITH_TABLE if has_table else VISUAL_REFERENCE


def references_visual(data: dict) -> bool:
    options = data.get("options")
    stimulus = data.get("stimulus")
    texts = [data.get("question_text"), stimulus.get("readable_text") if isinstance(stimulus, dict) else None]
    if isinstance(options, dict):
        texts.extend(options.values())
    pattern = _visual_pattern_for(stimulus)
    typed = registry.is_typed(stimulus)
    return any(
        pattern.search(text) or (not typed and IMAGE_LOCATION.search(text)) for text in texts if isinstance(text, str)
    )


REPEAT_MIN_CHARS = 120
REPEAT_OVERLAP = 0.6


def _readable_texts(data: dict) -> list[str]:
    stimulus = data.get("stimulus")
    texts = [data.get("question_text"), data.get("kesimpulan"), *(data.get("langkah") or []), *(data.get("options") or {}).values()]
    texts.append(stimulus.get("readable_text") if isinstance(stimulus, dict) else None)
    return [text for text in texts if isinstance(text, str)]


def raw_symbol_issue(data: dict) -> list[str]:
    texts = _readable_texts(data)
    if any(has_raw_notation(text) for text in texts):
        return ["Teks memakai simbol atau rumus mentah; tulis rumus dan simbol dengan kata agar terbaca pembaca layar."]
    return []


DANGLING_END = re.compile(r"(\.{2,}|…|_{2,})\s*$")


TRAILING_ELLIPSIS = re.compile(r"\s*(?:\.{2,}|…|_{2,})\s*$")
OPEN_ENDINGS = ("adalah", "yaitu", "ialah", "merupakan")


def repair_dangling_question(data: dict) -> dict:
    """Ganti titik-titik di ujung soal dengan pertanyaan lengkap ('adalah ...' menjadi 'adalah apa?', selain itu diberi tanda tanya)."""
    question = data.get("question_text")
    if not isinstance(question, str) or not DANGLING_END.search(question):
        return data
    stem = TRAILING_ELLIPSIS.sub("", question).rstrip()
    if not stem:
        return data
    ending = " apa?" if stem.split()[-1].lower().strip(",;:") in OPEN_ENDINGS else "?"
    return {**data, "question_text": stem + ending}


def dangling_question_issue(data: dict) -> list[str]:
    question = data.get("question_text")
    if isinstance(question, str) and DANGLING_END.search(question):
        return ["Soal berakhir menggantung dengan titik-titik atau garis kosong; akhiri dengan kalimat tanya atau perintah lengkap."]
    return []


STIMULUS_WORD = re.compile(r"\bstimulus\b", re.IGNORECASE)


def stimulus_word_issue(data: dict) -> list[str]:
    texts = [data.get("question_text"), data.get("kesimpulan"), *(data.get("langkah") or []), *(data.get("options") or {}).values()]
    if any(STIMULUS_WORD.search(text) for text in texts if isinstance(text, str)):
        return ["Jangan memakai kata 'stimulus' di soal, opsi, atau langkah; acu dengan 'keterangan tadi', 'cerita tadi', 'tabel tadi', atau 'gambar tadi' sesuai bentuknya."]
    return []


def stimulus_repeat_issue(data: dict) -> list[str]:
    stimulus = data.get("stimulus")
    question = str(data.get("question_text", ""))
    if not isinstance(stimulus, dict) or len(question) < REPEAT_MIN_CHARS:
        return []
    asked = set(re.findall(r"\w+", question.lower()))
    told = set(re.findall(r"\w+", str(stimulus.get("readable_text", "")).lower()))
    if asked and len(asked & told) / len(asked) >= REPEAT_OVERLAP:
        return ["Soal mengulang cerita atau data yang sudah ada di stimulus; soal cukup berisi pertanyaan."]
    return []


def _non_empty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def structure_issues(data: dict) -> list[str]:
    options = data.get("options")
    if not isinstance(options, dict) or set(options) != set(LABELS) or not all(map(_non_empty_str, options.values())):
        return ["Opsi harus tepat empat (A, B, C, D) dan masing-masing berupa teks tidak kosong."]
    if str(data.get("correct_option", "")).strip().upper() not in options:
        return ["correct_option harus salah satu dari opsi A-D."]
    langkah = data.get("langkah")
    if not isinstance(langkah, list) or not langkah or not all(map(_non_empty_str, langkah)):
        return ["Langkah penyelesaian harus berupa daftar teks tidak kosong."]
    if not _non_empty_str(data.get("question_text")) or not _non_empty_str(data.get("kesimpulan")):
        return ["Soal dan kesimpulan harus berupa teks tidak kosong."]
    stimulus = data.get("stimulus")
    if stimulus is not None and not _stimulus_shape_ok(stimulus):
        return [STIMULUS_TYPED_SHAPE_MESSAGE if registry.typed_names() else STIMULUS_SHAPE_MESSAGE]
    return []


STIMULUS_SHAPE_MESSAGE = "Stimulus harus null atau objek dengan readable_text tidak kosong."
STIMULUS_TYPED_SHAPE_MESSAGE = (
    "Stimulus harus null, objek dengan readable_text tidak kosong, atau objek bertipe dengan jenis dan spesifikasi."
)


def _stimulus_shape_ok(stimulus) -> bool:
    if not isinstance(stimulus, dict):
        return False
    return _non_empty_str(stimulus.get("readable_text")) or (registry.is_typed(stimulus) and isinstance(stimulus.get("spesifikasi"), dict))


def stimulus_level_issue(data: dict, level: int | None) -> list[str]:
    if level is None:
        return []
    has_stimulus = bool(data.get("stimulus"))
    if level >= 4 and not has_stimulus:
        return ["Soal C4 dan C5 wajib punya stimulus (teks, tabel, atau gambar); isi field stimulus, jangan null."]
    if level < 4 and has_stimulus:
        return ["Soal C1 sampai C3 tidak boleh punya stimulus; isi stimulus dengan null."]
    return []


def option_length_issue(data: dict) -> list[str]:
    options = data["options"]
    correct = str(data["correct_option"]).strip().upper()
    others = [len(str(text)) for label, text in options.items() if label != correct]
    if not others:
        return []
    own = len(str(options[correct]))
    if own > max(others) and own > config.OPTION_LENGTH_RATIO * (sum(others) / len(others)):
        return ["Opsi jawaban benar jauh lebih panjang daripada opsi lain; samakan panjang dan tingkat detail semua opsi."]
    return []


def visual_reference_issue(data: dict) -> list[str]:
    if references_visual(data):
        return ["Soal atau stimulus merujuk gambar, grafik, tabel, atau diagram; tulis semua data dalam teks."]
    return []


def code_issues(data: dict, level: int | None = None) -> list[str]:
    issues = structure_issues(data)
    if issues:
        return issues
    checkers = (
        visual_reference_issue, lambda soal: stimulus_level_issue(soal, level), option_length_issue,
        raw_symbol_issue, stimulus_repeat_issue, dangling_question_issue, stimulus_word_issue,
    )
    return [issue for check in checkers for issue in check(data)]
