from __future__ import annotations

import re
from dataclasses import dataclass, field

from quizzer import config

FRONT_MATTER = re.compile(
    r"^(tujuan pembelajaran|pertanyaan pemantik|kata kunci|peta konsep|pengantar( bab)?|tahukah kamu)\b", re.IGNORECASE
)
SOLUTION_START = re.compile(r"^(penyelesaian|jawab|jawaban|solusi|pembahasan)\b", re.IGNORECASE)
ATTACHED_TYPES = {"formula", "table", "image"}


@dataclass
class Segment:
    chapter_id: int
    title: str
    reading_order_start: int
    reading_order_end: int
    text: str
    context_text: str = ""
    blocks: list = field(default_factory=list)

    @property
    def labeled_text(self) -> str:
        return "\n".join(f"[{b['reading_order']}] {b['readable_text']}" for b in self.blocks)


def build_segments(chapter_id, blocks) -> list[Segment]:
    """Potong blok satu bab (urut reading_order) menjadi segmen menurut blok dan jumlah karakter; heading hanya memilih titik potong."""
    content = _drop_front_matter(blocks)
    if not content:
        return []
    allowed = _cut_allowed(content)
    cuts = _plan_cuts(content, allowed)
    if cuts and _chars(content[cuts[-1]:]) < config.SEGMENT_MIN_TAIL_CHARS:
        cuts.pop()
    segments = []
    for index, (start, end) in enumerate(zip([0, *cuts], [*cuts, len(content)])):
        part = content[start:end]
        context = content[max(0, start - config.OVERLAP_BLOCKS):start] if index else []
        segments.append(Segment(
            chapter_id=chapter_id,
            title=_title(part, index),
            reading_order_start=part[0]["reading_order"],
            reading_order_end=part[-1]["reading_order"],
            text="\n".join(b["readable_text"] for b in part),
            context_text="\n".join(b["readable_text"] for b in context),
            blocks=part,
        ))
    return segments


def span_text(blocks, order_start: int, order_end: int) -> str:
    """Teks blok pada rentang reading_order ditambah margin blok di kedua sisi, margin dikurangi bila melebihi SOURCE_MAX_CHARS."""
    rows = sorted(blocks, key=lambda b: b["reading_order"])
    inside = [i for i, b in enumerate(rows) if order_start <= b["reading_order"] <= order_end]
    if not inside:
        return ""
    low, high = inside[0], inside[-1] + 1
    start, end = max(0, low - config.SOURCE_MARGIN_BLOCKS), min(len(rows), high + config.SOURCE_MARGIN_BLOCKS)
    while (start < low or end > high) and len(_join(rows[start:end])) > config.SOURCE_MAX_CHARS:
        if start < low and low - start >= end - high:
            start += 1
        else:
            end -= 1
    return _join(rows[start:end])


def _chars(rows) -> int:
    return sum(len(b["readable_text"]) for b in rows)


def _join(rows) -> str:
    return "\n".join(b["readable_text"] for b in rows)


def _drop_front_matter(blocks) -> list[dict]:
    kept, skipping = [], False
    for block in blocks:
        if block["block_type"] == "heading":
            skipping = bool(FRONT_MATTER.match(block["readable_text"].strip()))
        if not skipping and block["readable_text"].strip():
            kept.append(block)
    return kept


def _cut_allowed(blocks) -> list[bool]:
    allowed = [False] * len(blocks)
    for i in range(1, len(blocks)):
        block = blocks[i]
        glued = (
            blocks[i - 1]["block_type"] == "heading"
            or block["block_type"] in ATTACHED_TYPES
            or SOLUTION_START.match(block["readable_text"].strip())
        )
        allowed[i] = not glued
    return allowed


def _plan_cuts(blocks, allowed) -> list[int]:
    sizes = [len(b["readable_text"]) for b in blocks]
    cuts, start = [], 0
    while True:
        end, size = start, 0
        while end < len(blocks) and size < config.SEGMENT_TARGET_CHARS:
            size += sizes[end]
            end += 1
        if end >= len(blocks):
            return cuts
        cut = _choose_cut(blocks, allowed, sizes, end, size)
        if cut >= len(blocks):
            return cuts
        cuts.append(cut)
        start = cut


def _choose_cut(blocks, allowed, sizes, end: int, size: int) -> int:
    first_allowed = None
    for index in range(end, len(blocks)):
        if first_allowed is not None and size > config.SEGMENT_MAX_CHARS:
            return first_allowed
        if size > config.SEGMENT_MAX_CHARS * config.SEGMENT_HARD_FACTOR:
            return index
        if allowed[index]:
            if blocks[index]["block_type"] == "heading":
                return index
            if first_allowed is None:
                first_allowed = index
        size += sizes[index]
    return first_allowed if first_allowed is not None else len(blocks)


def _title(part, index: int) -> str:
    for block in part:
        if block["block_type"] == "heading":
            return block["readable_text"].strip()
    return f"Bagian {index + 1}"
