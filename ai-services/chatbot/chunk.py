"""Konversi tiap block jadi satu vector langsung -- SATU block = SATU embedding, bukan digabung
beberapa block jadi satu chunk artifisial. `blocks` sudah datang tersegmentasi rapi dari pipeline
anotasi (satu block_type = satu unit makna: satu heading, satu paragraf, satu rumus, satu tabel,
satu gambar -- lihat `annotation/preprocess.py`), jadi tidak perlu chunking tambahan di atas itu,
dan tidak dibedakan perlakuan per block_type (heading/text/formula/table/image semua diperlakukan
sama, cuma teksnya beda).

Satu-satunya "pemrosesan" di sini: block NON-heading diberi prefix heading terdekat sebagai
konteks, supaya embedding-nya tidak kosong makna kalau block-nya pendek/berdiri sendiri (mis. satu
kalimat definisi tanpa konteks sub-bab apa dia berasal, bakal susah ditemukan lewat similarity)."""

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
    Satu block DB -> satu Chunk (satu vector nanti). `heading` dilacak berjalan sebagai konteks,
    bukan sebagai batas penggabungan."""
    current_heading = "Pembuka"
    chunks: list[Chunk] = []

    for block in blocks:
        if block["block_type"] == "heading":
            current_heading = block["readable_text"]
            text = block["readable_text"]
        else:
            text = f"{current_heading}: {block['readable_text']}"

        chunks.append(
            Chunk(
                chapter_id=chapter_id,
                heading=current_heading,
                block_ids=[block["id"]],
                reading_order_start=block["reading_order"],
                reading_order_end=block["reading_order"],
                text=text,
            )
        )

    return chunks
