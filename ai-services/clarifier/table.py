import re

from clarifier import config
from common import table_spec

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
TRIVIAL = {"0", "1"}


def _digits(token: str) -> str:
    return re.sub(r"[.,]", "", token)


def _numbers(text: str) -> set[str]:
    return {_digits(token) for token in NUMBER.findall(text)} - TRIVIAL


def _cell_text(spec: dict) -> str:
    return " ".join([str(spec.get("judul") or ""), *map(str, spec["kolom"]), *(str(cell) for row in spec["baris"] for cell in row)])


def build(spec, grounding_texts: list[str]) -> dict | None:
    """Tabel dari compose_answer beserta bacaannya dan temuan; tabel tidak valid atau berangka di luar sumber dibuang (tabel None); None bila tanpa tabel."""
    if spec in (None, {}, []):
        return None
    issues = table_spec.spec_issues(spec, config.TABLE_MAX_CHARS) if isinstance(spec, dict) and {"kolom", "baris"} <= set(spec) else ["tabel harus berisi judul, kolom, dan baris."]
    if not issues:
        known = _numbers(" ".join(grounding_texts))
        missing = sorted(_numbers(_cell_text(spec)) - known)
        if missing:
            issues = [f"angka pada tabel tidak ada di sumber atau ringkasan: {', '.join(missing)}."]
    if issues:
        return {"tabel": None, "tabel_bacaan": None, "tabel_ringkasan": None, "issues": issues}
    readable, _, summary = table_spec.narrate_spec(spec)
    return {
        "tabel": {"judul": spec["judul"].strip(), "kolom": list(spec["kolom"]), "baris": [list(row) for row in spec["baris"]]},
        "tabel_bacaan": readable, "tabel_ringkasan": summary, "issues": [],
    }
