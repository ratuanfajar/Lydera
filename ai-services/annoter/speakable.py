import re

from annoter.phrases import UNCERTAIN_READING
from common.notation_check import has_raw_notation

UNIT_NAMES = {
    "m": "meter", "cm": "sentimeter", "mm": "milimeter", "km": "kilometer", "g": "gram", "kg": "kilogram", "l": "liter",
    "s": "sekon", "detik": "detik", "menit": "menit", "jam": "jam",
}
FIXED_SLASHES = {("dan", "atau"): "dan atau", ("s", "d"): "sampai dengan"}
NUMBER_WORDS = dict(zip("0123456789", "nol satu dua tiga empat lima enam tujuh delapan sembilan".split()))
SUPERSCRIPTS = {
    "⁻¹": " pangkat minus satu", "⁻²": " pangkat minus dua", "⁻³": " pangkat minus tiga", "⁰": " pangkat nol",
    "¹": " pangkat satu", "²": " pangkat dua", "³": " pangkat tiga", "⁴": " pangkat empat", "⁵": " pangkat lima",
    "⁶": " pangkat enam", "⁷": " pangkat tujuh", "⁸": " pangkat delapan", "⁹": " pangkat sembilan", "ⁿ": " pangkat n",
}
SYMBOL_WORDS = {
    "→": " menuju ", "⟶": " menuju ", "⇒": " maka ", "∘": " komposisi ", "∞": " tak hingga ",
    "≤": " kurang dari atau sama dengan ", "≥": " lebih dari atau sama dengan ", "≠": " tidak sama dengan ",
    "≈": " kira-kira ", "±": " plus atau minus ", "÷": " dibagi ", "×": " kali ", "∈": " anggota ", "∪": " gabungan ",
    "∩": " irisan ", "∅": " himpunan kosong ",
}

DOUBLE_QUOTES = re.compile("[\"“”„]")
WRAPPED_SINGLE_QUOTES = re.compile(r"(?<![\w')\]])['‘]([^'’\n]+?)['’](?![\w'])")
SLASHED = re.compile(r"(?<![\w{/])(\w{1,6})/(\w{1,6})(?![\w/])")
MINUS_BEFORE_NUMBER = re.compile(r"(?<![\w)])[-−](?=\d)")
CARET_POWER = re.compile(r"\^\{?(-?)(\d+)\}?(?![\w/]|,\d)")
LETTER_MINUS_DIGIT = re.compile(r"\b[A-Za-z]-\d\b")
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,;:!?])(?!\.)")
LEFTOVER_SLASH = re.compile(r"\S/\S")


def speakable(text: str) -> str:
    """Ganti notasi mentah yang pasti pada deskripsi gambar dengan kata; yang ambigu dibiarkan agar ditandai."""
    text = DOUBLE_QUOTES.sub("", text)
    text = WRAPPED_SINGLE_QUOTES.sub(r"\1", text)
    for symbol, words in SUPERSCRIPTS.items():
        text = text.replace(symbol, words)
    text = CARET_POWER.sub(_caret_power, text)
    text = SLASHED.sub(_slashed, text)
    text = MINUS_BEFORE_NUMBER.sub(_minus, text)
    for symbol, words in SYMBOL_WORDS.items():
        text = text.replace(symbol, words)
    return SPACE_BEFORE_PUNCTUATION.sub(r"\1", re.sub(r"\s+", " ", text)).strip()


def description_issues(text: str) -> list[str]:
    issues = []
    if has_raw_notation(text) or LEFTOVER_SLASH.search(text) or LETTER_MINUS_DIGIT.search(text):
        issues.append("Deskripsi gambar masih memuat notasi mentah; periksa bacaannya.")
    if UNCERTAIN_READING.search(text):
        issues.append("Ada bagian gambar yang tidak terbaca; periksa terhadap gambar.")
    return issues


def _slashed(match: re.Match) -> str:
    left, right = match.group(1), match.group(2)
    low = (left.lower(), right.lower())
    if low in FIXED_SLASHES:
        return FIXED_SLASHES[low]
    if left.isdigit() and right.isdigit() and re.fullmatch(r"\d ", match.string[max(0, match.start() - 2):match.start()]):
        return match.group()
    if left.isdigit() or right.isdigit():
        return f"{left} per {right}"
    if low[0] in UNIT_NAMES and low[1] in UNIT_NAMES:
        return f"{UNIT_NAMES[low[0]]} per {UNIT_NAMES[low[1]]}"
    if len(left) == len(right) == 1:
        return f"{left} per {right}"
    return match.group()


def _caret_power(match: re.Match) -> str:
    sign, digits = match.groups()
    number = NUMBER_WORDS[digits] if len(digits) == 1 else digits
    return f" pangkat {'minus ' if sign else ''}{number}"


def _minus(match: re.Match) -> str:
    return " minus " if match.start() and match.string[match.start() - 1] == "," else "minus "
