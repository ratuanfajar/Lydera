from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

NOISE_TYPES = {"header", "footer", "page_number"}
MATH_SPAN = re.compile(r"\$\$.+?\$\$|\$.+?\$", re.DOTALL)


class Route(str, Enum):
    HEADING = "heading"
    TEXT = "text"
    FORMULA = "formula"
    TABLE = "table"
    IMAGE = "image"


@dataclass
class Segment:
    is_formula: bool
    content: str


@dataclass
class Block:
    route: Route
    order: int
    page: int
    text: str = ""
    segments: list[Segment] = field(default_factory=list)
    latex: str = ""
    level: int | None = None
    table_html: str = ""
    caption: str = ""
    image_path: Path | None = None


def preprocess(content_list_path: str | Path) -> list[Block]:
    """Ubah content_list.json MinerU menjadi blok ter-route siap dikonversi."""
    path = Path(content_list_path)
    items = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent

    blocks: list[Block] = []
    for item in items:
        if item.get("type") in NOISE_TYPES:
            continue
        block = normalize(item, base, len(blocks))
        if block is not None:
            blocks.append(block)
    return blocks


def normalize(item: dict, base: Path, order: int) -> Block | None:
    kind = item.get("type")
    page = item.get("page_idx", 0)
    if kind == "text":
        return normalize_text(item, order, page)
    if kind == "equation":
        return Block(Route.FORMULA, order, page, latex=strip_math_delims(item.get("text", "")))
    if kind == "table":
        return normalize_table(item, base, order, page)
    if kind in ("image", "chart"):
        return normalize_image(item, base, order, page)
    return None


def normalize_text(item: dict, order: int, page: int) -> Block | None:
    text = item.get("text", "").strip()
    if not text:
        return None
    level = item.get("text_level")
    route = Route.HEADING if level else Route.TEXT
    return Block(route, order, page, text=text, level=level, segments=split_math(text))


def normalize_table(item: dict, base: Path, order: int, page: int) -> Block:
    return Block(
        Route.TABLE, order, page,
        table_html=item.get("table_body", ""),
        caption=join_caption(item.get("table_caption")),
        image_path=resolve_image(item.get("img_path"), base),
    )


def normalize_image(item: dict, base: Path, order: int, page: int) -> Block:
    return Block(
        Route.IMAGE, order, page,
        caption=join_caption(item.get("image_caption") or item.get("chart_caption")),
        image_path=resolve_image(item.get("img_path"), base),
    )


def split_math(text: str) -> list[Segment]:
    segments: list[Segment] = []
    cursor = 0
    for match in MATH_SPAN.finditer(text):
        if match.start() > cursor:
            segments.append(Segment(False, text[cursor:match.start()]))
        segments.append(Segment(True, strip_math_delims(match.group())))
        cursor = match.end()
    if cursor < len(text):
        segments.append(Segment(False, text[cursor:]))
    return segments


def strip_math_delims(value: str) -> str:
    value = value.strip()
    if value.startswith("$$") and value.endswith("$$"):
        return value[2:-2].strip()
    if value.startswith("$") and value.endswith("$"):
        return value[1:-1].strip()
    return value


def join_caption(value) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return " ".join(part for part in value if part)
    return str(value)


def resolve_image(relative: str | None, base: Path) -> Path | None:
    if not relative:
        return None
    return (base / relative).resolve()
