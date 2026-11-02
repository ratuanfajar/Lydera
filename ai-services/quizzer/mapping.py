from collections import Counter

from common import llm
from quizzer import config, prompts

LOTS_LEVELS = (1, 2, 3)
HOTS_LEVELS = (4, 5)

COMPATIBLE_KINDS = {
    1: {"definisi", "rumus", "konsep"},
    2: {"definisi", "konsep", "miskonsepsi", "perbandingan", "rumus"},
    3: {"rumus", "prosedur", "aplikasi"},
    4: {"miskonsepsi", "perbandingan", "prosedur", "aplikasi"},
    5: {"perbandingan", "aplikasi", "miskonsepsi"},
}


def level_quota(lots_count: int, hots_count: int, offset: int = 0) -> dict[int, int]:
    return {**_spread(lots_count, LOTS_LEVELS, offset), **_spread(hots_count, HOTS_LEVELS, offset)}


def plan_slots(chapters: list[dict], propose=None) -> tuple[list[dict], dict[int, dict]]:
    """Petakan poin ke slot (bab, level). LLM mengusulkan, kode menegakkan kuota guru dan mengisi kekurangan."""
    for index, chapter in enumerate(chapters):
        chapter["quota"] = level_quota(chapter["lots_count"], chapter["hots_count"], index)
    proposals = (propose or propose_with_llm)(chapters)
    slots, notes = [], {}
    for chapter in chapters:
        proposed = proposals.get(chapter["chapter_id"], {})
        chapter_slots, reused = _assign(chapter, proposed)
        slots.extend(chapter_slots)
        notes[chapter["chapter_id"]] = {"mapping": "llm" if proposed else "pengisi", "reused_points": reused}
    return slots, notes


def propose_with_llm(chapters: list[dict]) -> dict:
    candidates = [c for c in chapters if c["points"]]
    fits = sum(len(c["points"]) for c in candidates) <= config.MAPPING_POINT_LIMIT
    proposals = {}
    for group in [candidates] if fits else [[c] for c in candidates]:
        if group and sum(len(c["points"]) for c in group) <= config.MAPPING_POINT_LIMIT:
            try:
                proposals.update(_parse(_call(group)))
            except Exception:
                continue
    return proposals


def _call(chapters: list[dict]) -> dict:
    return llm.complete_json(
        prompts.MAPPING_SYSTEM, prompts.mapping_input(chapters), model=config.QUIZ_MODEL,
        max_tokens=config.MAPPING_MAX_TOKENS, required_keys=["pemetaan"], effort=config.MAPPING_EFFORT,
    )


def _parse(data: dict) -> dict[int, dict[int, list[str]]]:
    parsed: dict[int, dict[int, list[str]]] = {}
    for item in data["pemetaan"] if isinstance(data["pemetaan"], list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("bab"), int) or not isinstance(item.get("level"), int):
            continue
        ids = [i for i in item.get("poin", []) if isinstance(i, str)]
        parsed.setdefault(item["bab"], {}).setdefault(item["level"], []).extend(ids)
    return parsed


def _assign(chapter: dict, proposed: dict[int, list[str]]) -> tuple[list[dict], int]:
    points = {p["id"]: p for p in chapter["points"]}
    uses, load = Counter(), Counter()
    chosen: dict[int, list[tuple[str, bool]]] = {level: [] for level in chapter["quota"]}

    def take(level: int, point_id: str, reused: bool) -> None:
        chosen[level].append((point_id, reused))
        uses[point_id] += 1
        load[points[point_id]["segment_index"]] += 1

    for level, quota in chapter["quota"].items():
        for point_id in proposed.get(level, []):
            point = points.get(point_id)
            if len(chosen[level]) < quota and point and not uses[point_id] and point["kind"] in COMPATIBLE_KINDS[level]:
                take(level, point_id, False)
    for level, quota in chapter["quota"].items():
        while len(chosen[level]) < quota and points:
            point_id = _fill(points, level, uses, load)
            take(level, point_id, uses[point_id] > 0)

    slots = [
        {"chapter_id": chapter["chapter_id"], "level": level, "point": points[point_id], "reused": reused}
        for level, entries in chosen.items() for point_id, reused in entries
    ]
    return slots, sum(1 for slot in slots if slot["reused"])


def _fill(points: dict, level: int, uses: Counter, load: Counter) -> str:
    unused = [pid for pid in points if not uses[pid]]
    pool = unused or [pid for pid in points if uses[pid] == min(uses[p] for p in points)]
    compatible = [pid for pid in pool if points[pid]["kind"] in COMPATIBLE_KINDS[level]]
    return min(compatible or pool, key=lambda pid: (load[points[pid]["segment_index"]], points[pid]["order_start"]))


def _spread(count: int, levels: tuple[int, ...], offset: int) -> dict[int, int]:
    base, extra = divmod(count, len(levels))
    quota = {level: base for level in levels}
    for index in range(extra):
        quota[levels[(index + offset) % len(levels)]] += 1
    return quota
