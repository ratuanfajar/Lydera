from __future__ import annotations

import re

from common import math_text
from common.notation_check import has_raw_notation

MAX_MARKUP_CHARS = 4000
MAX_FORMULAS = 10
ALLOWED_COMMANDS = frozenset(
    "frac dfrac tfrac sqrt cdot cdots ldots dots times div pm mp leq geq neq le ge ne approx equiv sim cong parallel perp "
    "angle triangle circ overline widehat overrightarrow left right begin end array cases pmatrix matrix text mathrm mathbb "
    "alpha beta gamma delta epsilon theta lambda mu pi rho sigma tau phi varphi omega Delta Sigma Omega Theta Phi Pi "
    "infty in notin subset subseteq supset cup cap emptyset setminus forall exists neg land lor to rightarrow leftarrow "
    "Rightarrow Leftrightarrow leftrightarrow mapsto log ln sin cos tan cot sec csc arcsin arccos arctan lim sum prod int "
    "min max gcd mod bmod quad qquad".split()
)
SYMBOL_WORDS = {"=": " sama dengan ", "+": " tambah ", "^": " pangkat ", "_": " sub ", "°": " derajat ", "√": " akar ", "×": " kali ", "π": " pi "}

_COMMAND = re.compile(r"\\([A-Za-z]+)")
_FRACTION = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_DANGLING_SCRIPT = re.compile(r"[\^_]\s*(?:$|[})\]])")
_LEFTOVER = re.compile(r"[\\{}*#|`]")


def derive_message(text: str) -> tuple[str, str | None, list[str]]:
    """Turunkan (bacaan, markup, temuan) dari teks berisi LaTeX $...$; markup None bila tanpa rumus atau ada temuan."""
    spans = [content for is_math, content in math_text.split_math(text) if is_math]
    outside = " ".join(content for is_math, content in math_text.split_math(text) if not is_math)
    if not spans:
        return (plain_text(text), None, math_text.latex_issues(text)) if "$" in text else _without_math(text)
    issues = _markup_issues(text, spans)
    if has_raw_notation(outside.replace("$", "")):
        issues.append("Ada simbol matematika di luar tanda dolar.")
    if issues:
        return plain_text(text), None, issues
    found: list[str] = []
    try:
        spoken = math_text.readable_texts([text], found)[0]
    except Exception as error:
        return plain_text(text), None, [f"Verbalizer rumus gagal: {type(error).__name__}"]
    return spoken, (None if found else text), found


def plain_text(text: str) -> str:
    """Bacaan darurat tanpa verbalizer: simbol diganti kata dan tidak ada sisa sintaks LaTeX."""
    text = text.replace("\\$", " dolar ").replace("$", " ")
    text = _FRACTION.sub(r" \1 per \2 ", text)
    text = _SQRT.sub(r" akar \1 ", text)
    text = _COMMAND.sub(lambda match: f" {match.group(1)} ", text)
    for symbol, word in SYMBOL_WORDS.items():
        text = text.replace(symbol, word)
    return math_text.normalize_spacing(_LEFTOVER.sub(" ", text))


def clean_field(text) -> str:
    """Bersihkan bidang yang harus berupa kata (label, justification, pertanyaan lanjutan) dari simbol dan tanda dolar."""
    text = text if isinstance(text, str) else ""
    return plain_text(text) if "$" in text or has_raw_notation(text) else text


def _without_math(text: str) -> tuple[str, None, list[str]]:
    if has_raw_notation(text.replace("\\$", " dolar ")):
        return plain_text(text), None, ["Ada simbol matematika di luar tanda dolar."]
    return text, None, []


def _markup_issues(text: str, spans: list[str]) -> list[str]:
    issues = math_text.latex_issues(text)
    if len(text) > MAX_MARKUP_CHARS:
        issues.append("Teks jawaban terlalu panjang untuk ditampilkan sebagai rumus.")
    if len(spans) > MAX_FORMULAS:
        issues.append(f"Jumlah rumus melebihi {MAX_FORMULAS}.")
    if any(_DANGLING_SCRIPT.search(span.strip()) for span in spans):
        issues.append("Pangkat atau subskrip tanpa isi.")
    forbidden = sorted({name for span in spans for name in _COMMAND.findall(span) if name not in ALLOWED_COMMANDS})
    if forbidden:
        issues.append(f"Perintah LaTeX tidak diizinkan: {', '.join(forbidden)}.")
    return issues
