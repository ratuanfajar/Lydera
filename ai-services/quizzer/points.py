import json
import re

from common import cache, llm
from quizzer import config, prompts
from quizzer.segment import Segment

KINDS = ("definisi", "rumus", "prosedur", "konsep", "miskonsepsi", "perbandingan", "aplikasi")
QUOTE_MAX_CHARS = 200


def extract_segment(segment: Segment) -> list[dict]:
    key = (segment.context_text, segment.labeled_text, config.QUIZ_MODEL, config.QUIZ_PROMPT_VERSION)
    cached = cache.get("quiz_points", *key)
    if cached is None:
        points = _extract_or_split(segment)
        cached = json.dumps(points, ensure_ascii=False)
        cache.put("quiz_points", cached, *key)
    return json.loads(cached)


def _extract_or_split(segment: Segment) -> list[dict]:
    try:
        data = llm.complete_json(
            prompts.POINTS_SYSTEM, prompts.points_input(segment), model=config.QUIZ_MODEL,
            max_tokens=config.POINTS_MAX_TOKENS, required_keys=["poin"], effort=config.POINTS_EFFORT,
        )
    except llm.TruncatedOutputError:
        if len(segment.blocks) < 2:
            raise
        first, second = _halves(segment)
        return extract_segment(first) + extract_segment(second)
    return _normalize(segment, data["poin"])


def _halves(segment: Segment) -> tuple[Segment, Segment]:
    middle = len(segment.blocks) // 2
    return _sub_segment(segment, segment.blocks[:middle], segment.context_text), _sub_segment(
        segment, segment.blocks[middle:], "\n".join(b["readable_text"] for b in segment.blocks[max(0, middle - 2):middle])
    )


def _sub_segment(segment: Segment, blocks: list[dict], context: str) -> Segment:
    return Segment(
        chapter_id=segment.chapter_id, title=segment.title,
        reading_order_start=blocks[0]["reading_order"], reading_order_end=blocks[-1]["reading_order"],
        text="\n".join(b["readable_text"] for b in blocks), context_text=context, blocks=blocks,
    )


def _normalize(segment: Segment, raw_points) -> list[dict]:
    orders = {b["reading_order"] for b in segment.blocks}
    points = []
    for item in raw_points if isinstance(raw_points, list) else []:
        if not isinstance(item, dict) or not str(item.get("teks", "")).strip():
            continue
        start = _order(item.get("mulai"), orders, segment.reading_order_start)
        end = _order(item.get("selesai"), orders, segment.reading_order_end)
        points.append({
            "text": str(item["teks"]).strip(),
            "kind": item.get("jenis") if item.get("jenis") in KINDS else "konsep",
            "order_start": min(start, end),
            "order_end": max(start, end),
            "quote": str(item.get("kutipan", "")).strip()[:QUOTE_MAX_CHARS],
        })
    return points[: config.MAX_POINTS_PER_SEGMENT]


def _order(value, orders: set, default: int) -> int:
    return value if isinstance(value, int) and value in orders else default


def dedupe(points: list[dict]) -> list[dict]:
    """Buang poin kembar (kemiripan kata) dari segmen yang sama atau bertetangga, karena overlap segmen bisa menghasilkan poin sama."""
    tokens = [set(re.findall(r"\w+", point["text"].lower())) for point in points]
    kept: list[int] = []
    for index, point in enumerate(points):
        neighbors = [j for j in kept if points[j]["segment_index"] >= point["segment_index"] - 1]
        if any(_jaccard(tokens[index], tokens[j]) >= config.POINT_DUPLICATE_SIMILARITY for j in neighbors):
            continue
        kept.append(index)
    return [points[i] for i in kept]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0
