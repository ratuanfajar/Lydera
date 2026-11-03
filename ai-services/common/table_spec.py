import json

from common import math_text
from common.math_text import HTML_TAG

MAX_CELL_CHARS = 200
MARKDOWN_CHARS = "*#|`"


def _cells(spec: dict) -> list:
    return [spec.get("judul"), *spec["kolom"], *(cell for row in spec["baris"] for cell in row)]


def _outside_math(cell: str) -> str:
    return "".join(content for is_math, content in math_text.split_math(cell) if not is_math)


def _non_empty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def spec_issues(spec: dict, max_chars: int) -> list[str]:
    """Pemeriksa tabel terstruktur {judul, kolom, baris} bersama Quizzer dan Clarifier: struktur, ukuran, tanpa tag atau markdown, LaTeX berpasangan."""
    if not isinstance(spec, dict) or not _non_empty(spec.get("judul")):
        return ["judul tabel wajib diisi."]
    issues = math_text.table_issues(spec)
    if issues:
        return issues
    cells = _cells(spec)
    if any(not isinstance(cell, str) for cell in cells) or any(not _non_empty(name) for name in spec["kolom"]):
        return ["nama kolom dan semua sel tabel harus berupa teks, nama kolom tidak boleh kosong."]
    if len(json.dumps(spec, ensure_ascii=False)) > max_chars or any(len(cell) > MAX_CELL_CHARS for cell in cells):
        return ["tabel terlalu besar."]
    if any(HTML_TAG.search(cell) or any(char in _outside_math(cell) for char in MARKDOWN_CHARS) for cell in cells):
        return ["sel tabel tidak boleh memuat tag atau markdown; tulis rumus sebagai LaTeX di antara tanda dolar."]
    return list(dict.fromkeys(issue for cell in cells for issue in math_text.latex_issues(cell)))


def narrate_spec(spec: dict) -> tuple[str, dict, str]:
    """(bacaan telusur, tabel yang diucapkan, ringkasan) dari tabel yang lolos spec_issues; rumus di sel diverbalisasi."""
    spoken = math_text.spoken_table(spec)
    return math_text.table_readable(spoken), spoken, math_text.table_summary(spoken, spec["judul"].strip())
