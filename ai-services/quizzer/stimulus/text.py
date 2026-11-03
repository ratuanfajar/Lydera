import json
import re

from common import math_text
from common.math_text import HTML_TAG
from quizzer import config

UNSAFE_CHARS = ("$", "\\", "`", "*", "#", "|", "^", "<", ">", "%", "=", "+", "×", "÷", "≥", "≤", "√", "π")
KEY_NAME = re.compile(r"^[A-Za-z0-9_]{1,40}$")


def shape_issues(spec) -> list[str]:
    if not isinstance(spec, dict):
        return ["Spesifikasi harus berupa objek."]
    leaves, depth, strings = _walk(spec, 1)
    issues = []
    if not _keys_ok(spec):
        issues.append("Spesifikasi memuat nama kunci yang tidak wajar.")
    if leaves > config.STIMULUS_MAX_LEAVES or len(json.dumps(spec, ensure_ascii=False)) > config.STIMULUS_MAX_CHARS:
        issues.append("Spesifikasi terlalu besar.")
    if depth > config.STIMULUS_MAX_DEPTH:
        issues.append("Spesifikasi bersarang terlalu dalam.")
    if any(HTML_TAG.search(text) or any(char in text for char in UNSAFE_CHARS) for text in strings):
        issues.append("Spesifikasi memuat markup atau simbol; tulis semua label dan nama dengan kata biasa (mis. 'lima puluh persen').")
    return issues


def _keys_ok(value) -> bool:
    if isinstance(value, dict):
        return all(KEY_NAME.match(str(key)) and _keys_ok(child) for key, child in value.items())
    if isinstance(value, list):
        return all(_keys_ok(child) for child in value)
    return True


def _walk(value, depth: int) -> tuple[int, int, list[str]]:
    if isinstance(value, dict):
        children = list(value.values())
    elif isinstance(value, list):
        children = value
    else:
        return 1, depth, [value] if isinstance(value, str) else []
    leaves, deepest, strings = 0, depth, []
    for child in children:
        child_leaves, child_depth, child_strings = _walk(child, depth + 1)
        leaves, deepest, strings = leaves + child_leaves, max(deepest, child_depth), strings + child_strings
    return leaves, deepest, strings


def latex_text_issues(text) -> list[str]:
    """Teks biasa yang boleh memuat rumus LaTeX berpasangan di antara tanda dolar; simbol dan markup di luar rumus ditolak."""
    if not isinstance(text, str) or not text.strip():
        return ["teks harus berupa teks biasa tidak kosong."]
    outside = "".join(content for is_math, content in math_text.split_math(text) if not is_math)
    issues = list(math_text.latex_issues(text))
    if HTML_TAG.search(text) or any(char in outside for char in UNSAFE_CHARS):
        issues.append("teks memuat markup atau simbol di luar rumus; tulis dengan kata atau pakai LaTeX di antara tanda dolar.")
    return issues
