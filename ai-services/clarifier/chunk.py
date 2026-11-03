"""Konversi block jadi chunk untuk embedding: block dikemas menurut ukuran karakter, heading hanya dipakai sebagai titik potong pilihan."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from clarifier.formula_text import normalize_formula

MAX_CHUNK_CHARS = 1200
TARGET_CHUNK_CHARS = 600
MIN_TAIL_CHARS = 250
OVERLAP_MAX_CHARS = 300
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
    Chunk berisi block berurutan sampai sekitar TARGET_CHUNK_CHARS lalu dipotong di heading berikutnya, atau di batas block sebelum MAX_CHUNK_CHARS;
    block pertama tiap chunk tidak pernah sama dengan block pertama chunk lain karena itu dipakai sebagai rujukan sitasi."""
    units = [unit for section in _sections(blocks) if not _is_metadata(section) for unit in section["units"]]
    groups = _merge_tail(_pack(units))
    return [_chunk(chapter_id, group) for group in _with_overlap(groups)]


def _sections(blocks: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for block in blocks:
        if block["block_type"] == "heading":
            current = {"heading": block["readable_text"], "units": []}
            sections.append(current)
        elif current is None:
            current = {"heading": "Pembuka", "units": []}
            sections.append(current)
        current["units"].append({"block": block, "heading": current["heading"]})
    return sections


def _is_metadata(section: dict) -> bool:
    return any(_METADATA.search(text) for text in (section["heading"], *(unit["block"]["readable_text"] for unit in section["units"])))


def _is_heading(unit: dict) -> bool:
    return unit["block"]["block_type"] == "heading"


def _length(unit: dict) -> int:
    return len(unit["block"]["readable_text"])


def _pack(units: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    current: list[dict] = []
    size = 0
    for unit in units:
        too_long = size + _length(unit) > MAX_CHUNK_CHARS
        heading_cut = _is_heading(unit) and size >= TARGET_CHUNK_CHARS
        if any(not _is_heading(held) for held in current) and (too_long or heading_cut):
            groups.append(current)
            current = [groups[-1].pop()] if len(groups[-1]) > 1 and _is_heading(groups[-1][-1]) else []
            size = _size(current)
        current.append(unit)
        size += _length(unit)
    if current:
        groups.append(current)
    return groups


def _merge_tail(groups: list[list[dict]]) -> list[list[dict]]:
    if len(groups) > 1 and _size(groups[-1]) < MIN_TAIL_CHARS and _size(groups[-2]) + _size(groups[-1]) <= MAX_CHUNK_CHARS:
        groups[-2].extend(groups.pop())
    return groups


def _size(group: list[dict]) -> int:
    return sum(_length(unit) for unit in group)


def _with_overlap(groups: list[list[dict]]) -> list[list[dict]]:
    result = [groups[0]] if groups else []
    for previous, group in zip(groups, groups[1:]):
        last = previous[-1]
        carry = len(previous) > 1 and not _is_heading(last) and _length(last) <= OVERLAP_MAX_CHARS
        result.append([last, *group] if carry else group)
    return result


def _chunk(chapter_id: int, group: list[dict]) -> Chunk:
    blocks = [unit["block"] for unit in group]
    heading = group[0]["heading"]
    parts = [] if _is_heading(group[0]) else [f"{heading}:"]
    parts += [f"{block['readable_text']}:" if block["block_type"] == "heading" else block["readable_text"] for block in blocks]
    return Chunk(
        chapter_id=chapter_id,
        heading=heading,
        block_ids=[block["id"] for block in blocks],
        reading_order_start=blocks[0]["reading_order"],
        reading_order_end=blocks[-1]["reading_order"],
        text=" ".join(parts).removesuffix(":"),
        formula_norm=FORMULA_SEPARATOR.join(_unique(formula for block in blocks for formula in _formulas(block))),
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
