import re

from common.notation_check import has_raw_notation
from evaluaizer import config

META_PHRASES = re.compile(r"catatan (langkah|pengerjaan)|langkah kunci|kunci jawaban|materi sumber", re.IGNORECASE)
RAW_QUANTITY = re.compile(r"\d[A-Za-z]\b")
FOREIGN_SCRIPT = re.compile("[Ͱ-῿⺀-￿]")
MARKDOWN = re.compile(r"[*#`|]|^\s*[-•]\s", re.MULTILINE)


STRAY_MARKS = re.compile(r"[?!]")
DOUBLE_WORD = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)
DOUBLE_WORD_ALLOWED = {"sama", "kali", "bagi", "demi"}
UNPUNCTUATED = re.compile(r"[\W_]+")
LEADING_NUMBER = re.compile(r"^\s*\d+\s*[.)]\s*")


def result_issues(result: dict, student_steps: list[str]) -> list[str]:
    issues = _field_issues(result, student_steps)
    keterangan = result.get("keterangan")
    if not isinstance(keterangan, str) or not keterangan.strip():
        return issues + ["keterangan tidak boleh kosong."]
    if len(keterangan) > config.MAX_KETERANGAN_CHARS:
        issues.append("keterangan terlalu panjang; cukup satu sampai dua kalimat.")
    return issues + _text_issues(keterangan)


def _field_issues(result: dict, student_steps: list[str]) -> list[str]:
    determinable, step, quote = result.get("dapat_ditentukan"), result.get("langkah_ke"), result.get("kutipan")
    if not isinstance(determinable, bool):
        return ["dapat_ditentukan harus true atau false."]
    if not determinable:
        if step is not None or quote is not None:
            return ["Bila dapat_ditentukan false, langkah_ke dan kutipan harus null."]
        return []
    verdicts = result.get("penilaian_langkah")
    if not isinstance(verdicts, list) or len(verdicts) != len(student_steps) or not all(isinstance(v, bool) for v in verdicts):
        return [f"penilaian_langkah harus daftar true atau false sebanyak {len(student_steps)} langkah siswa."]
    first_wrong = verdicts.index(False) + 1 if False in verdicts else None
    if step != first_wrong:
        return ["langkah_ke harus nomor false pertama pada penilaian_langkah, atau null bila semua true."]
    if step is None:
        return [] if quote is None else ["Tanpa langkah_ke, kutipan harus null."]
    if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= len(student_steps):
        return [f"langkah_ke harus null atau nomor langkah siswa antara 1 dan {len(student_steps)}."]
    if not isinstance(quote, str) or not quote.strip() or len(quote) > config.MAX_KUTIPAN_CHARS:
        return ["kutipan harus berupa isi langkah siswa yang ditunjuk, tidak kosong dan tidak terlalu panjang."]
    if not _grounded(quote, student_steps[step - 1]):
        return [f"kutipan tidak ditemukan pada langkah siswa nomor {step}; salin isi langkah itu persis."]
    return []


def strip_numbering(quote: str) -> str:
    return LEADING_NUMBER.sub("", quote.strip())


def _grounded(quote: str, step: str) -> bool:
    flat_quote, flat_step = _flat(strip_numbering(quote)), _flat(step)
    return bool(flat_quote) and flat_quote in flat_step


def _flat(text: str) -> str:
    return UNPUNCTUATED.sub("", text).lower()


def _text_issues(text: str) -> list[str]:
    issues = []
    if has_raw_notation(text) or RAW_QUANTITY.search(text):
        issues.append("Teks memakai simbol atau rumus mentah; tulis dengan kata agar terbaca pembaca layar.")
    if FOREIGN_SCRIPT.search(text):
        issues.append("Teks memuat huruf atau kata bukan Bahasa Indonesia; tulis seluruhnya dalam Bahasa Indonesia.")
    if MARKDOWN.search(text):
        issues.append("Teks memakai markdown atau butir; tulis kalimat biasa.")
    if STRAY_MARKS.search(text):
        issues.append("Teks memuat tanda tanya atau seru; tulis kalimat pernyataan.")
    if any(match.group(1).lower() not in DOUBLE_WORD_ALLOWED for match in DOUBLE_WORD.finditer(text)):
        issues.append("Teks memuat kata yang berulang berurutan; periksa dan perbaiki kalimatnya.")
    if META_PHRASES.search(text):
        issues.append("Teks memuat istilah internal tentang catatan atau langkah kunci; jelaskan langsung isi pelajarannya.")
    return issues
