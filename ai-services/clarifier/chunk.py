"""Konversi block jadi chunk untuk embedding: semua block di bawah satu heading digabung jadi
satu Chunk, bukan satu block satu Chunk (lihat evaluasi retrieval chatbot)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    chapter_id: int
    heading: str
    block_ids: list[int] = field(default_factory=list)
    reading_order_start: int = 0
    reading_order_end: int = 0
    text: str = ""


def build_chunks(chapter_id: int, blocks: list[dict]) -> list[Chunk]:
    """`blocks`: dict dengan field id, block_type, readable_text, reading_order, urut reading_order.
    Batas chunk = tiap heading; block sebelum heading pertama masuk chunk "Pembuka"."""
    sections: list[dict] = []
    current: dict | None = None

    for block in blocks:
        if block["block_type"] == "heading":
            if current and current["block_ids"]:
                sections.append(current)
            current = {"heading": block["readable_text"], "block_ids": [block["id"]], "texts": [],
                      "reading_order_start": block["reading_order"], "reading_order_end": block["reading_order"]}
            continue
        if current is None:
            current = {"heading": "Pembuka", "block_ids": [], "texts": [],
                      "reading_order_start": block["reading_order"], "reading_order_end": block["reading_order"]}
        current["block_ids"].append(block["id"])
        current["texts"].append(block["readable_text"])
        current["reading_order_end"] = block["reading_order"]

    if current and current["block_ids"]:
        sections.append(current)

    return [
        Chunk(
            chapter_id=chapter_id,
            heading=s["heading"],
            block_ids=s["block_ids"],
            reading_order_start=s["reading_order_start"],
            reading_order_end=s["reading_order_end"],
            text=f"{s['heading']}: " + " ".join(s["texts"]) if s["texts"] else s["heading"],
        )
        for s in sections
    ]
