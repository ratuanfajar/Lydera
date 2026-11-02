from __future__ import annotations

import re
from dataclasses import dataclass

SUBBAB_PATTERN = re.compile(r"^[A-Z]\.\s")


@dataclass
class Segment:
    chapter_id: int
    title: str
    reading_order_start: int
    reading_order_end: int
    text: str


def build_segments(chapter_id, blocks) -> list[Segment]:
    """Pecah block satu bab (urut reading_order) jadi segmen berdasar heading berpola 'A. ...'/'B. ...'.

    Block sebelum sub-bab pertama (judul bab, tujuan pembelajaran, dst) tidak masuk segmen apa pun --
    dianggap materi pengantar, bukan sumber soal.
    """
    groups: list[list[dict]] = []
    for block in blocks:
        if block["block_type"] == "heading" and SUBBAB_PATTERN.match(block["readable_text"]):
            groups.append([block])
        elif groups:
            groups[-1].append(block)

    return [
        Segment(
            chapter_id=chapter_id,
            title=group[0]["readable_text"],
            reading_order_start=group[0]["reading_order"],
            reading_order_end=group[-1]["reading_order"],
            text="\n".join(b["readable_text"] for b in group),
        )
        for group in groups
    ]
