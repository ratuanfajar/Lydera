import re

RAW_SYMBOLS = set("→{}^√×−≤≥≠∘∠△⊥∥$")
RAW_FORMULA = re.compile(r"\s[=+\-*/]\s|[=^]|[A-Za-z]\([^)\s]{1,12}\)")


def has_raw_notation(text: str) -> bool:
    return bool(RAW_SYMBOLS & set(text) or RAW_FORMULA.search(text))
