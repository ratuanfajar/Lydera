from __future__ import annotations

import itertools
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import config as common_config
from common import guardrails, llm, svg_raster
from common.parallel import parallel_map
from common.resilience import Breaker, is_systemic
from quizzer import checks, config, generate, mapping, points, readable, segment, shuffle, validate
from quizzer.stimulus import registry

logger = logging.getLogger(__name__)

NO_TEXT_REASON = "Bab tidak memiliki teks yang dapat dijadikan sumber soal."
NO_POINTS_REASON = "Tidak ada poin materi yang berhasil diekstrak dari bab ini."
UNAVAILABLE_REASON = "Layanan model tidak tersedia."


class QuizzerUnavailable(RuntimeError):
    pass


def compute_for_quiz(chapters: list[dict], on_progress=None, seed=None, extract=None, propose=None) -> dict:
    """Jalankan pipeline untuk semua bab; hasilnya {"items", "report"} dan satu slot gagal tidak membatalkan yang lain."""
    rng = random.Random(seed)
    breaker = Breaker(config.BREAKER_THRESHOLD)
    prepared = _prepare(chapters, extract or points.extract_segment, breaker)
    plan_input = [
        {"chapter_id": c["chapter_id"], "cp_text": c["cp_text"], "hots_count": c["hots_count"],
         "lots_count": c["lots_count"], "points": prepared[c["chapter_id"]]["points"]}
        for c in chapters
    ]
    slots, notes = mapping.plan_slots(plan_input, propose)
    _assign_targets(slots, rng)
    context = {c["chapter_id"]: c for c in chapters}
    results = _run_slots(slots, context, on_progress, breaker)
    items = [r["item"] for r in results if r["item"]]
    report = _report(chapters, prepared, notes, results, items)
    for item in items:
        item.pop("slot")
    return {"items": items, "report": report}


def _prepare(chapters: list[dict], extract, breaker: Breaker) -> dict[int, dict]:
    prepared = {c["chapter_id"]: {"segments": segment.build_segments(c["chapter_id"], c["blocks"]), "points": [],
                                  "errors": []} for c in chapters}
    jobs = [(chapter_id, index, seg) for chapter_id, entry in prepared.items() for index, seg in enumerate(entry["segments"])]
    outputs = parallel_map(lambda job: _try(_guarded(extract, breaker), job[2]), jobs)
    for (chapter_id, index, _), output in zip(jobs, outputs):
        if isinstance(output, Exception):
            logger.error("ekstraksi poin segmen %s bab %s gagal: %r", index + 1, chapter_id, output)
            prepared[chapter_id]["errors"].append(f"Segmen {index + 1}: {_safe_error(output)}")
            continue
        prepared[chapter_id]["points"].extend({**p, "chapter_id": chapter_id, "segment_index": index} for p in output)
    counter = itertools.count(1)
    for entry in prepared.values():
        entry["points"] = points.dedupe(entry["points"])
        for point in entry["points"]:
            point["id"] = f"p{next(counter)}"
    return prepared


def _assign_targets(slots: list[dict], rng: random.Random) -> None:
    by_chapter: dict[int, list[dict]] = {}
    for slot in slots:
        by_chapter.setdefault(slot["chapter_id"], []).append(slot)
    for chapter_slots in by_chapter.values():
        for slot, target in zip(chapter_slots, shuffle.balanced_targets(len(chapter_slots), rng)):
            slot["target"] = target
            slot["rng"] = random.Random(rng.random())


def _run_slots(slots: list[dict], context: dict, on_progress, breaker: Breaker) -> list[dict]:
    if not slots:
        return []
    results: list[dict | None] = [None] * len(slots)
    workers = max(1, min(common_config.LLM_MAX_WORKERS, len(slots)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_slot_safe, slot, context[slot["chapter_id"]], breaker=breaker): index for index, slot in enumerate(slots)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
            if on_progress:
                on_progress()
    return results


def _run_slot_safe(slot: dict, chapter: dict, extra_correction: str = "", breaker: Breaker | None = None) -> dict:
    try:
        return {"slot": slot, "item": _run_slot(slot, chapter, extra_correction, breaker), "error": None}
    except Exception as exc:
        logger.exception("slot bab %s level C%s gagal", slot["chapter_id"], slot["level"])
        return {"slot": slot, "item": None, "error": _safe_error(exc)}


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, QuizzerUnavailable) or is_systemic(exc):
        return UNAVAILABLE_REASON
    if isinstance(exc, llm.TruncatedOutputError):
        return "Keluaran model terpotong."
    if isinstance(exc, llm.ContentFilterError):
        return "Ditolak filter keamanan model."
    if isinstance(exc, ValueError) and str(exc).startswith(INVALID_PREFIX):
        return str(exc)[:300]
    return f"Kesalahan saat memproses ({type(exc).__name__})."


SOURCE_INJECTION_FLAG = "Teks sumber memuat kalimat yang meniru instruksi kepada model; periksa sumber dan soal."
INVALID_PREFIX = "soal tidak valid"
HOTS_LEVEL = 4


def _run_slot(slot: dict, chapter: dict, extra_correction: str = "", breaker: Breaker | None = None) -> dict:
    point = slot["point"]
    source = segment.span_text(chapter["blocks"], point["order_start"], point["order_end"]) or point["quote"] or point["text"]
    visuals = segment.visual_kinds(chapter["blocks"], point["order_start"], point["order_end"]) if slot["level"] >= HOTS_LEVEL else ()
    correction, repaired, best, last_error = extra_correction, False, None, None
    for attempt in range(config.MAX_GENERATIONS_PER_SLOT):
        last = attempt == config.MAX_GENERATIONS_PER_SLOT - 1
        if breaker is not None and breaker.tripped:
            if best is None:
                raise QuizzerUnavailable(UNAVAILABLE_REASON)
            break
        try:
            candidate = _attempt(slot, chapter, source, correction, last, visuals)
        except Exception as exc:
            if breaker is not None:
                breaker.failure(exc)
            last_error = exc
            logger.exception("percobaan %s slot bab %s level C%s gagal", attempt + 1, slot["chapter_id"], slot["level"])
            continue
        if breaker is not None:
            breaker.success()
        if candidate["repair"]:
            _log_rejected(slot, candidate)
        if candidate["valid"]:
            best = candidate
        if candidate["repair"] and not last:
            correction, repaired = _correction(candidate["repair"], extra_correction), True
            continue
        break
    if best is None:
        if last_error is not None:
            raise last_error
        raise ValueError(f"{INVALID_PREFIX}: " + "; ".join(candidate["repair"]))
    return _slot_item(slot, best, repaired)


def _log_rejected(slot: dict, candidate: dict) -> None:
    stimulus = json.dumps(candidate["data"].get("stimulus"), ensure_ascii=False)[:2000]
    logger.warning("kandidat bab %s level C%s ditolak: %s | stimulus=%s", slot["chapter_id"], slot["level"], candidate["repair"], stimulus)


def _slot_item(slot: dict, best: dict, repaired: bool) -> dict:
    flagged = best["repair"] + best["flag"]
    return {
        "slot": slot, "chapter_id": slot["chapter_id"], "level": slot["level"], "data": best["data"],
        "source_point": slot["point"]["text"], "repaired": repaired, "reused": slot["reused"], "issues": flagged,
        "review_priority": "high" if flagged else "normal",
        "validation_notes": "\n".join(flagged) or None,
    }


def _attempt(slot: dict, chapter: dict, source: str, correction: str, last: bool, visuals: tuple = ()) -> dict:
    extra = {"visuals": visuals} if visuals else {}
    data = generate.generate_soal(slot["point"], source, slot["level"], chapter["cp_text"], correction, **extra)
    repair = checks.structure_issues(data) or readable.typed_stimulus_issues(data)
    if repair:
        return {"data": data, "valid": False, "repair": repair, "flag": []}
    data = checks.repair_dangling_question(data)
    repair = readable.markup_issues(data)
    if repair and not last:
        return {"data": data, "valid": False, "repair": repair, "flag": []}
    try:
        data, spoken_flags = readable.derive(data)
    except svg_raster.RenderError as exc:
        return {"data": data, "valid": False, "repair": [f"Gambar tidak dapat dirender: {exc}"], "flag": []}
    repair = repair + checks.code_issues(data, slot["level"])
    data = shuffle.reorder_options(data, slot["target"], slot["rng"])
    if repair and not last:
        return {"data": data, "valid": True, "repair": repair, "flag": spoken_flags}
    verification = validate.verify_soal(source, data, (data.get("stimulus") or {}).get("readable_text", ""))
    if not last and validate.is_blocking(verification, data):
        return {"data": data, "valid": True, "repair": verification["issues"], "flag": spoken_flags + verification["unavailable"]}
    flag = spoken_flags + verification["issues"] + verification["unavailable"] + _source_flags(source)
    return {"data": data, "valid": True, "repair": repair, "flag": flag}


def _source_flags(source: str) -> list[str]:
    return [SOURCE_INJECTION_FLAG] if guardrails.injection_markers(source, strict=False) else []


def _correction(issues: list[str], extra: str) -> str:
    lines = [f"- {issue}" for issue in issues]
    return "\n".join(([extra] if extra else []) + ["Perbaiki masalah berikut:", *lines])


def _chapter_report(chapter: dict, entry: dict, note: dict, results: list[dict], items: list[dict]) -> dict:
    chapter_id = chapter["chapter_id"]
    chapter_items = [i for i in items if i["chapter_id"] == chapter_id]
    used = {i["slot"]["point"]["id"] for i in chapter_items}
    failed = [
        {"level": r["slot"]["level"], "point": r["slot"]["point"]["text"][:120], "error": r["error"]}
        for r in results if r["slot"]["chapter_id"] == chapter_id and r["item"] is None
    ]
    return {
        "chapter_id": chapter_id,
        "segments": len(entry["segments"]),
        "points_total": len(entry["points"]),
        "points_used": len(used),
        "requested": {"lots": chapter["lots_count"], "hots": chapter["hots_count"]},
        "generated": {"lots": sum(1 for i in chapter_items if i["level"] <= 3),
                      "hots": sum(1 for i in chapter_items if i["level"] >= 4)},
        "failed": failed,
        "reused_points": sum(1 for i in chapter_items if i["reused"]),
        "unused_points": [p["text"][:120] for p in entry["points"] if p["id"] not in used][:10],
        "mapping": note.get("mapping"),
        "extraction_errors": entry["errors"],
        "skipped_reason": None if entry["points"] else (NO_POINTS_REASON if entry["segments"] else NO_TEXT_REASON),
    }


def _report(chapters, prepared, notes, results, items) -> dict:
    entries = [
        _chapter_report(chapter, prepared[chapter["chapter_id"]], notes.get(chapter["chapter_id"], {}), results, items)
        for chapter in chapters
    ]
    return {
        "chapters": entries,
        "summary": {
            "generated": len(items),
            "failed": sum(1 for r in results if r["item"] is None),
            "repaired": sum(1 for i in items if i["repaired"]),
            "high_priority": sum(1 for i in items if i["review_priority"] == "high"),
        },
    }


def _guarded(fn, breaker: Breaker):
    def call(*args):
        if breaker.tripped:
            raise QuizzerUnavailable(UNAVAILABLE_REASON)
        try:
            result = fn(*args)
        except Exception as exc:
            breaker.failure(exc)
            raise
        breaker.success()
        return result

    return call


def _try(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        return exc


PRACTICE_MAX_LEVEL = 3
PRACTICE_TYPED_ISSUE = "Latihan hanya boleh tanpa stimulus atau dengan stimulus teks."


def generate_practice(topic: str, source_text: str, level: int, rng: random.Random | None = None) -> dict:
    """Satu soal latihan dari teks sumber; lolos hanya bila tanpa temuan sama sekali, selain itu {"soal": None, "issues": [...]}."""
    rng = rng or random.Random()
    slot = {
        "chapter_id": 0, "level": min(max(level, 1), PRACTICE_MAX_LEVEL), "reused": False, "rng": rng, "target": rng.choice(shuffle.LABELS),
        "point": {"id": "latihan", "kind": "konsep", "text": topic, "order_start": 0, "order_end": 0},
    }
    correction, issues = "", []
    for _ in range(config.MAX_GENERATIONS_PER_SLOT):
        try:
            candidate = _attempt(slot, {"cp_text": ""}, source_text, correction, False)
        except Exception as exc:
            logger.exception("percobaan latihan gagal")
            issues = [f"Kesalahan saat membuat soal ({type(exc).__name__})."]
            continue
        issues = candidate["repair"] + candidate["flag"]
        if registry.is_typed(candidate["data"].get("stimulus")):
            issues.append(PRACTICE_TYPED_ISSUE)
        if candidate["valid"] and not issues:
            return {"soal": candidate["data"], "issues": []}
        correction = _correction(issues, "")
    return {"soal": None, "issues": issues}
