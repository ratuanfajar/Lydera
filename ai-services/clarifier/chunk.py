"""Konversi block jadi chunk untuk embedding: semua block di bawah satu heading digabung jadi
satu Chunk, bukan satu block satu Chunk (lihat evaluasi retrieval chatbot)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from clarifier.formula_text import normalize_formula

MAX_CHUNK_CHARS = 1500
FORMULA_SEPARATOR = ";"

_METADATA = re.compile(r"\bISBN\b|Dilarang memperbanyak|Hak Cipta Dilindungi", re.IGNORECASE)
_INLINE_MATH = re.compile(r"\$([^$]+)\$")


@dataclass
class Chunk:
    chapter_id: int
    heading: str
    block_ids: list[int] = field(default_factory=list)
    reading_order_start: int = 0
    reading_order_end: int = 0
    text: str = ""
    formula_norm: str = ""


def build_chunks(chapter_id: int, blocks: list[dict]) -> list[Chunk]:
    """`blocks`: dict dengan field id, block_type, readable_text, reading_order, source_markup (opsional), urut reading_order.
    Batas chunk = tiap heading; block sebelum heading pertama masuk chunk "Pembuka". Section yang lebih
    panjang dari MAX_CHUNK_CHARS dipecah di batas block; section metadata penerbit (ISBN, hak cipta) dilewati."""
    chunks: list[Chunk] = []
    for section in _sections(blocks):
        if not _is_metadata(section):
            chunks.extend(_split(chapter_id, section))
    return chunks


def _sections(blocks: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for block in blocks:
        if block["block_type"] == "heading":
            if current:
                sections.append(current)
            current = {"heading": block["readable_text"], "heading_id": block["id"], "heading_order": block["reading_order"], "entries": []}
            continue
        if current is None:
            current = {"heading": "Pembuka", "heading_id": None, "heading_order": block["reading_order"], "entries": []}
        current["entries"].append(block)
    if current:
        sections.append(current)
    return sections


def _is_metadata(section: dict) -> bool:
    return any(_METADATA.search(text) for text in (section["heading"], *(entry["readable_text"] for entry in section["entries"])))


def _split(chapter_id: int, section: dict) -> list[Chunk]:
    heading_id = section["heading_id"]
    if not section["entries"]:
        return [Chunk(chapter_id, section["heading"], [heading_id], section["heading_order"], section["heading_order"], section["heading"])]
    groups: list[list[dict]] = [[]]
    size = 0
    for entry in section["entries"]:
        length = len(entry["readable_text"])
        if groups[-1] and size + length > MAX_CHUNK_CHARS:
            groups.append([])
            size = 0
        groups[-1].append(entry)
        size += length
    return [_chunk(chapter_id, section, group, with_heading=index == 0) for index, group in enumerate(groups)]


def _chunk(chapter_id: int, section: dict, entries: list[dict], with_heading: bool) -> Chunk:
    heading_ids = [section["heading_id"]] if with_heading and section["heading_id"] is not None else []
    first_order = section["heading_order"] if with_heading else entries[0]["reading_order"]
    return Chunk(
        chapter_id=chapter_id,
        heading=section["heading"],
        block_ids=[*heading_ids, *(entry["id"] for entry in entries)],
        reading_order_start=first_order,
        reading_order_end=entries[-1]["reading_order"],
        text=f"{section['heading']}: " + " ".join(entry["readable_text"] for entry in entries),
        formula_norm=FORMULA_SEPARATOR.join(_unique(formula for entry in entries for formula in _formulas(entry))),
    )


def _formulas(block: dict) -> list[str]:
    markup = block.get("source_markup") or ""
    if block["block_type"] == "formula":
        found = [markup]
    elif block["block_type"] == "text":
        found = _INLINE_MATH.findall(markup)
    else:
        found = []
    return [formula for formula in (normalize_formula(item) for item in found) if formula]


def _unique(items) -> list[str]:
    return list(dict.fromkeys(items))
