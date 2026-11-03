import re

RAW_SYMBOLS = set("→{}^√×−≤≥≠∘∠△⊥∥$")
RAW_FORMULA = re.compile(r"\s[=+\-*/]\s|[=^]|[A-Za-z]\([^)\s]{1,12}\)")


def raw_notation_snippets(text: str) -> list[str]:
    return [*sorted(RAW_SYMBOLS & set(text)), *(match.group(0).strip() for match in RAW_FORMULA.finditer(text))]


def has_raw_notation(text: str) -> bool:
    return bool(RAW_SYMBOLS & set(text) or RAW_FORMULA.search(text))
