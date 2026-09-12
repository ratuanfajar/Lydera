from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import paths

paths.setup()

import config
import context
import generate
import segment
import validate


def compute_for_chapter(chapter_id, blocks, hots_count, lots_count) -> list[tuple[dict, dict]]:
    """Jalankan Chain 0-4 untuk satu bab, tanpa menyentuh DB. Mengembalikan list (data, hasil_validasi)
    per soal -- pemanggil (`backend/app/tasks/quiz_tasks.py`) yang menyimpan hasilnya.

    `blocks` iterable of dict/row dengan field reading_order, block_type, readable_text (urut
    reading_order), dibaca pemanggil dari DB.

    Map (ringkas tiap segmen) dan Generation+Validation (tiap soal) dijalankan paralel -- keduanya
    independen satu sama lain dalam satu bab (segmen tidak saling butuh; soal cuma butuh segmen +
    chapter_summary yang sudah pasti selesai lebih dulu). Reduce tetap satu panggilan tunggal
    (butuh semua ringkasan Map bab ini).
    """
    segments = segment.build_segments(chapter_id, blocks)
    if not segments:
        raise RuntimeError(f"chapter {chapter_id}: tidak ada sub-bab berpola 'A. ...' untuk dijadikan soal")

    summaries = _parallel_map(context.summarize_segment, segments)
    chapter_summary = context.summarize_chapter(summaries)

    plan = _allocate(segments, hots_count, lots_count)
    return _parallel_map(lambda item: _generate_and_validate(item, chapter_summary), plan)


def _generate_and_validate(item: tuple, chapter_summary: str) -> tuple[dict, dict]:
    seg, bloom_level = item
    data = generate.generate_soal(seg, chapter_summary, bloom_level)
    stim_text = (data.get("stimulus") or {}).get("readable_text", "")
    result = validate.validate_soal(seg, data["question_text"], data["options"], data["correct_option"], stim_text)
    return data, result


def _parallel_map(fn, items: list) -> list:
    """Sama seperti `[fn(item) for item in items]`, cuma dieksekusi paralel sebesar LLM_MAX_WORKERS.
    Urutan hasil tetap sama seperti sekuensial (pool.map, bukan as_completed)."""
    workers = max(1, min(config.LLM_MAX_WORKERS, len(items)))
    if workers == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


def _allocate(segments, hots_count, lots_count) -> list[tuple]:
    """Sebar target soal ke segmen secara round-robin. LOTS -> Bloom C2, HOTS -> Bloom C5 (default)."""
    plan = [(segments[i % len(segments)], 2) for i in range(lots_count)]
    plan += [(segments[i % len(segments)], 5) for i in range(hots_count)]
    return plan
