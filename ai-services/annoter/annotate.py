import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from annoter import config as annoter_config
from annoter import image, table
from annoter.phrases import FORMULA_UNREADABLE
from annoter.preprocess import Block, Route, preprocess
from annoter.priority import escalate, image_priority, table_flagged
from annoter.resilience import Breaker, is_systemic
from common import config, formula
from common.math_text import join_spoken, spell_greek, strip_tags

logger = logging.getLogger("annoter")


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
    image_kind: str = ""
    ringkasan: str = ""
    tabel: dict | None = None


@dataclass
class WindowResult:
    blocks: list[Annotated]
    failed: int
    attempted: int


def annotate_window(content_list_path, breaker: Breaker | None = None) -> WindowResult:
    """Konversi blok MinerU menjadi konten siap-talkback; blok berpanggilan LLM yang gagal disimpan kosong dan dihitung."""
    blocks = preprocess(content_list_path)
    breaker = breaker or Breaker(annoter_config.BREAKER_THRESHOLD)
    workers = max(1, min(config.LLM_MAX_WORKERS, len(blocks)))
    if workers == 1:
        outcomes = [_annotate_guarded(block, blocks, i, breaker) for i, block in enumerate(blocks)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(lambda i: _annotate_guarded(blocks[i], blocks, i, breaker), range(len(blocks))))
    failed = sum(failed for _, failed in outcomes)
    return WindowResult([annotated for annotated, _ in outcomes], failed, sum(_uses_llm(block) for block in blocks))


def _annotate_guarded(block: Block, blocks: list[Block], index: int, breaker: Breaker) -> tuple[Annotated, bool]:
    if not _uses_llm(block):
        return annotate_block(block, blocks, index), False
    if breaker.tripped:
        return failed_block(block), True
    try:
        annotated = annotate_block(block, blocks, index)
    except Exception as error:
        breaker.failure(error)
        logger.error("blok %s (%s) gagal: %s: %s", block.order, block.route.value, type(error).__name__, error)
        return failed_block(block), True
    breaker.success()
    return annotated, block.route == Route.TEXT and FORMULA_UNREADABLE in annotated.readable_text


def _uses_llm(block: Block) -> bool:
    return block.route in (Route.FORMULA, Route.TABLE, Route.IMAGE) or (
        block.route == Route.TEXT and any(segment.is_formula for segment in block.segments)
    )


def annotate_block(block: Block, blocks: list[Block], index: int) -> Annotated:
    if block.route == Route.IMAGE:
        return _image(block, _neighbor_text(blocks, index))
    return ANNOTATORS[block.route](block)


def failed_block(block: Block) -> Annotated:
    if block.route == Route.TEXT:
        return _annotated(block, _inline_text(block, lambda latex: FORMULA_UNREADABLE), "high", source_markup=block.text)
    return _annotated(block, "", "high", **FAILED_SOURCES[block.route](block))


def _neighbor_text(blocks: list[Block], index: int) -> str:
    parts = []
    for offset in (-1, 1):
        neighbor = index + offset
        if 0 <= neighbor < len(blocks) and blocks[neighbor].route in (Route.TEXT, Route.HEADING):
            parts.append(blocks[neighbor].text)
    return " ".join(part for part in parts if part)


def _image_name(block: Block) -> str:
    return block.image_path.name if block.image_path else ""


def _annotated(block: Block, text: str, priority: str, **extra) -> Annotated:
    return Annotated(block.route.value, block.order, block.page, text, priority, **extra)


def _heading(block: Block) -> Annotated:
    return _annotated(block, spell_greek(strip_tags(block.text)), escalate(block, False), heading_level=block.level)


def _text(block: Block) -> Annotated:
    issues: list[str] = []
    text = _inline_text(block, lambda latex: _convert_inline(latex, issues))
    return _annotated(block, text, escalate(block, bool(issues)), source_markup=block.text)


def _formula(block: Block) -> Annotated:
    spoken, issues = formula.convert_checked(block.latex)
    return _annotated(block, spoken, escalate(block, bool(issues)), source_markup=block.latex)


def _table(block: Block) -> Annotated:
    result = table.linearize_table(block)
    return _annotated(
        block, result.text, escalate(block, table_flagged(result)), ringkasan=result.ringkasan, tabel=result.tabel,
        **_table_source(block),
    )


def _image(block: Block, context: str) -> Annotated:
    result = image.annotate_image(block, context)
    return _annotated(block, result.text, image_priority(result), image_kind=result.kind, **_image_source(block))


def _inline_text(block: Block, convert) -> str:
    parts = [(True, convert(segment.content)) if segment.is_formula else (False, strip_tags(segment.content)) for segment in block.segments]
    return join_spoken(parts)


def _convert_inline(latex: str, issues: list[str]) -> str:
    try:
        spoken, found = formula.convert_checked(latex)
    except Exception as error:
        if is_systemic(error):
            raise
        logger.error("rumus inline gagal: %s: %s", type(error).__name__, error)
        spoken, found = FORMULA_UNREADABLE, ["Rumus inline tidak terbaca."]
    issues.extend(found)
    return spoken


def _formula_source(block: Block) -> dict:
    return {"source_markup": block.latex}


def _table_source(block: Block) -> dict:
    return {"source_markup": block.table_html, "caption": block.caption, "image_file": _image_name(block)}


def _image_source(block: Block) -> dict:
    return {"caption": block.caption, "image_file": _image_name(block)}


ANNOTATORS = {Route.HEADING: _heading, Route.TEXT: _text, Route.FORMULA: _formula, Route.TABLE: _table}
FAILED_SOURCES = {Route.FORMULA: _formula_source, Route.TABLE: _table_source, Route.IMAGE: _image_source}


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    result = annotate_window(argv[0])
    destination = Path(argv[1]) if len(argv) > 1 else Path("annotated.json")
    destination.write_text(json.dumps([asdict(item) for item in result.blocks], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(result.blocks)} blok -> {destination}; gagal {result.failed} dari {result.attempted} blok berpanggilan LLM")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
