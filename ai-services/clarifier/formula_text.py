from __future__ import annotations

import re

MIN_FORMULA_CHARS = 5

_UNICODE_TO_ASCII = {
    "²": "^2", "³": "^3", "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "≤": "<=", "≥": ">=", "≠": "!=",
    "√": "sqrt", "π": "pi", "∞": "inf",
}
_UNICODE_TABLE = str.maketrans(_UNICODE_TO_ASCII)
_COMMAND_TO_ASCII = {
    "times": "*", "cdot": "*", "div": "/", "leq": "<=", "le": "<=", "geq": ">=", "ge": ">=", "neq": "!=", "ne": "!=",
    "pm": "+-", "infty": "inf", "circ": "o",
}

_SPACING = re.compile(r"\\[,;:! ]|\\(?:quad|qquad)(?![A-Za-z])")
_WRAPPERS = re.compile(r"\\(?:left|right|textstyle|displaystyle|mathrm|mathbf|mathit|text|bigg?|Bigg?)(?![A-Za-z])")
_ENVIRONMENT = re.compile(r"\\(?:begin|end)\s*\{[^{}]*\}(?:\s*\{[lrc|\s]*\})?")
_FRACTION = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_SCRIPT = re.compile(r"([\^_])\s*\{([^{}]*)\}")
_ROW_BREAK = re.compile(r"\\\\")
_PLAIN_POWER = re.compile(r"\^(-?\d{2,}|-\d+)")
_PLAIN_FRACTION = re.compile(r"(?<![\w.)])(\([^()]*\)|[\w.]+)/(\([^()]*\)|[\w.]+)(?![\w.(])")
_COMMAND = re.compile(r"\\([A-Za-z]+)")
_NOISE = re.compile(r"[{}\\&~\s]")

_OPERATORS = set("=<>^+-*/")
_FUNCTION_WORDS = {"sin", "cos", "tan", "log", "ln", "lim", "sqrt"}
_PUNCTUATION = ".,;:?!"
_WORD = re.compile(r"[A-Za-z]+")


def normalize_formula(text: str) -> str:
    """Bentuk kanonik huruf kecil tanpa spasi untuk LaTeX buku maupun rumus ketikan siswa, supaya dapat dicocokkan sebagai substring."""
    text = text.translate(_UNICODE_TABLE).replace("**", "^")
    text = _ROW_BREAK.sub(";", text)
    text = _ENVIRONMENT.sub("", _WRAPPERS.sub("", _SPACING.sub("", text)))
    previous = None
    while previous != text:
        previous = text
        text = _SQRT.sub(r"sqrt(\1)", text)
        text = _FRACTION.sub(r"(\1)/(\2)", text)
        text = _SCRIPT.sub(_script, text)
    text = _COMMAND.sub(lambda match: _COMMAND_TO_ASCII.get(match.group(1), match.group(1)), text)
    text = _NOISE.sub("", text).lower()
    return _PLAIN_FRACTION.sub(_plain_fraction, _PLAIN_POWER.sub(r"^(\1)", text))


def formula_spans(question: str) -> list[str]:
    spans: list[str] = []
    run: list[str] = []
    for token in [*question.split(), ""]:
        if _is_math_token(token):
            run.append(token.strip(_PUNCTUATION))
            continue
        span = normalize_formula(" ".join(run))
        if len(span) >= MIN_FORMULA_CHARS and any(char in _OPERATORS for char in span) and span not in spans:
            spans.append(span)
        run = []
    return spans


def _plain_fraction(match: re.Match) -> str:
    return "/".join(side if side.startswith("(") else f"({side})" for side in match.groups())


def _script(match: re.Match) -> str:
    content = "".join(match.group(2).split())
    return f"{match.group(1)}{content}" if len(content) == 1 else f"{match.group(1)}({content})"


def _is_math_token(token: str) -> bool:
    stripped = token.strip(_PUNCTUATION)
    if not stripped:
        return False
    words = _WORD.findall(stripped)
    if any(len(word) >= 4 and word.lower() not in _FUNCTION_WORDS for word in words):
        return False
    if stripped.lower() in _FUNCTION_WORDS:
        return True
    if stripped.isalpha():
        return len(stripped) == 1 or (stripped.isupper() and len(stripped) <= 3)
    return True
