import html
import json
import re
from dataclasses import dataclass, field

from annoter import prompts
from annoter.phrases import UNREADABLE
from annoter.speakable import speakable
from common import cache, config, llm
from common.math_text import latex_issues, spoken_table, strip_tags, table_issues, table_readable, table_summary

MARKDOWN_CHARS = re.compile(r"[*#`|_]")
MAX_TOPIC_CHARS = 200
THOUSANDS_SEPARATOR = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")
MATH_SPAN = re.compile(r"\$.+?\$", re.DOTALL)
NO_TITLE_MARKERS = frozenset({"tidak ada", "tanpa judul", "-", "null", "none"})
SYSTEM = prompts.table_system()


@dataclass
class TableResult:
    text: str
    ringkasan: str = ""
    tabel: dict | None = None
    issues: list[str] = field(default_factory=list)


def linearize_table(block) -> TableResult:
    if not (block.image_path and block.image_path.exists()):
        return TableResult(block.caption)
    key = (block.image_path.stem, config.VISION_MODEL, config.TABLE_PROMPT_VERSION)
    cached = cache.get("table", *key)
    if cached is None:
        user = prompts.table_input(block.caption, block.table_html)
        data = request(SYSTEM, user, block.image_path)
        cache.put("table", json.dumps(data, ensure_ascii=False), *key)
    else:
        data = json.loads(cached)
    return from_response(data, block.table_html)


def request(system: str, user: str, image_path) -> dict:
    return llm.complete_vision_json(
        system, user, image_path, max_tokens=config.TABLE_MAX_TOKENS, required_keys=("deskripsi",),
    )


def from_response(data: dict, ocr_html: str, compare_ocr: bool = True) -> TableResult:
    observed = data.get("pengamatan") if isinstance(data.get("pengamatan"), dict) else {}
    topic = str(data.get("topik") or "").strip()
    raw, issues = _structure(observed), topic_issues(topic)
    if raw is None or table_issues(raw):
        issues.append("Struktur tabel tidak valid; mode telusur sel tidak tersedia.")
        return TableResult(str(data["deskripsi"]).strip(), topic, None, issues)
    for cell in [raw["judul"] or "", *raw["kolom"], *(cell for row in raw["baris"] for cell in row)]:
        issues.extend(latex_issues(cell))
        if UNREADABLE in cell.lower():
            issues.append("Ada sel yang tidak terbaca pada gambar; periksa tabel terhadap gambar.")
    tabel = _speakable_table(spoken_table(raw, issues))
    if _differs_from_ocr(tabel, ocr_html):
        issues.append("Ukuran tabel berbeda dari hasil OCR; periksa sel terhadap gambar.")
    if compare_ocr and _numbers_dropped_from_ocr(raw, ocr_html):
        issues.append("Ada angka di hasil OCR yang tidak ada di sel tabel; periksa terhadap gambar.")
    return TableResult(table_readable(tabel), table_summary(tabel, topic), tabel, list(dict.fromkeys(issues)))


def topic_issues(topic: str) -> list[str]:
    issues = []
    if MARKDOWN_CHARS.search(topic):
        issues.append("Topik tabel memuat simbol markdown.")
    if len(topic) > MAX_TOPIC_CHARS:
        issues.append("Topik tabel terlalu panjang; cukup satu kalimat.")
    return issues


def _structure(observed: dict) -> dict | None:
    columns, rows = observed.get("kolom"), observed.get("baris")
    if not isinstance(columns, list) or not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        return None
    title = _cell(observed.get("judul"))
    title = "" if title.lower() in NO_TITLE_MARKERS else title
    return {
        "judul": title or None, "kolom": [_cell(cell) for cell in columns],
        "baris": [[_cell(cell) for cell in row] for row in rows],
    }


def _cell(value) -> str:
    return "" if value is None else str(value).strip()


def _differs_from_ocr(tabel: dict, ocr_html: str) -> bool:
    rows = re.findall(r"<tr\b.*?</tr>", ocr_html, re.DOTALL | re.IGNORECASE)
    if not rows:
        return False
    columns = sum(int(span or 1) for span in re.findall(r"<t[dh]\b(?:[^>]*?colspan=\"?(\d+))?", rows[0]))
    return columns != len(tabel["kolom"]) or not len(tabel["baris"]) <= len(rows) <= len(tabel["baris"]) + 2


def _numbers_dropped_from_ocr(raw: dict, ocr_html: str) -> bool:
    ocr = _numbers(html.unescape(strip_tags(ocr_html, " ")))
    cells = " ".join([*raw["kolom"], *(cell for row in raw["baris"] for cell in row)])
    return bool(ocr - _numbers(cells))


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", THOUSANDS_SEPARATOR.sub("", MATH_SPAN.sub(" ", text))))


def _speakable_table(tabel: dict) -> dict:
    return {
        "judul": speakable(tabel["judul"]) if tabel["judul"] else None,
        "kolom": [speakable(name) for name in tabel["kolom"]],
        "baris": [[speakable(cell) for cell in row] for row in tabel["baris"]],
    }
