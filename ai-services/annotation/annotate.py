import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import config
import formula
import image
import table
from preprocess import Route, preprocess


@dataclass
class Annotated:
    block_type: str
    reading_order: int
    page: int
    readable_text: str
    review_priority: str = "normal"
    heading_level: int | None = None
    source_markup: str = ""
    caption: str = ""
    image_file: str = ""


def annotate(content_list_path) -> list[Annotated]:
    """Konversi seluruh blok MinerU menjadi konten siap-talkback, terurut baca."""
    blocks = preprocess(content_list_path)
    workers = max(1, min(config.MAX_WORKERS, len(blocks)))
    if workers == 1:
        return [annotate_block(block, blocks, i) for i, block in enumerate(blocks)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda i: annotate_block(blocks[i], blocks, i), range(len(blocks))))


def annotate_block(block, blocks, index) -> Annotated:
    priority = review_priority(block)
    if block.route == Route.HEADING:
        heading = normalize_spacing(strip_tags(block.text))
        return Annotated("heading", block.order, block.page, heading, priority, heading_level=block.level)
    if block.route == Route.TEXT:
        return Annotated("text", block.order, block.page, render_text(block), priority, source_markup=block.text)
    if block.route == Route.FORMULA:
        spoken = formula.convert_formula(block.latex)
        return Annotated("formula", block.order, block.page, spoken, priority, source_markup=block.latex)
    if block.route == Route.TABLE:
        return Annotated("table", block.order, block.page, table.linearize_table(block), priority,
                         source_markup=block.table_html, caption=block.caption, image_file=image_name(block))
    caption_text = image.caption_image(block, neighbor_text(blocks, index))
    return Annotated("image", block.order, block.page, caption_text, priority,
                     caption=block.caption, image_file=image_name(block))


def review_priority(block) -> str:
    if block.route in (Route.HEADING, Route.TEXT):
        return "low"
    if block.route == Route.TABLE and table_degraded(block.table_html):
        return "high"
    if block.route == Route.IMAGE and not block.caption:
        return "high"
    return "normal"


def table_degraded(html: str) -> bool:
    if "�" in html:
        return True
    cells = re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)
    if not cells:
        return False
    empty = sum(1 for cell in cells if not cell.strip())
    return empty / len(cells) > 0.3


def render_text(block) -> str:
    rendered = []
    for segment in block.segments:
        if segment.is_formula:
            rendered.append(formula.convert_formula(segment.content))
        else:
            rendered.append(strip_tags(segment.content))
    return normalize_spacing("".join(rendered))


def neighbor_text(blocks, index) -> str:
    parts = []
    for offset in (-1, 1):
        neighbor = index + offset
        if 0 <= neighbor < len(blocks) and blocks[neighbor].route in (Route.TEXT, Route.HEADING):
            parts.append(blocks[neighbor].text)
    return " ".join(part for part in parts if part)


def image_name(block) -> str:
    return block.image_path.name if block.image_path else ""


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def normalize_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


if __name__ == "__main__":
    result = annotate(sys.argv[1])
    destination = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("annotated.json")
    payload = [asdict(item) for item in result]
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(result)} blok -> {destination}")
