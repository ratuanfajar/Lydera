from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from quiz import paths

paths.setup()
from annotation import config
from quiz import context
from quiz import generate
from quiz import segment
from quiz import validate
from parallel import parallel_map


def compute_for_chapter(chapter_id, blocks, hots_count, lots_count, on_progress=None) -> list[tuple[dict, dict]]:
    """Jalankan Chain 0-4 untuk satu bab. Mengembalikan list (data, hasil_validasi) per soal."""
    segments = segment.build_segments(chapter_id, blocks)
    if not segments:
        raise RuntimeError(f"chapter {chapter_id}: tidak ada sub-bab berpola 'A. ...' untuk dijadikan soal")

    summaries = parallel_map(context.summarize_segment, segments)
    chapter_summary = context.summarize_chapter(summaries)

    plan = _allocate(segments, hots_count, lots_count)
    # return _parallel_map(
    #     lambda item: _generate_and_validate(item, chapter_summary), 
    #     plan,
    #     on_progress=on_progress
    # )
    return _parallel_map_with_progress(
        lambda item: _generate_and_validate(item, chapter_summary), 
        plan,
        on_progress=on_progress
    )

def _parallel_map_with_progress(fn, items: list, on_progress=None) -> list:
    workers = max(1, min(config.LLM_MAX_WORKERS, len(items)))
    if not items:
        return []

    results = [None] * len(items)
    
    if workers == 1:
        for idx, item in enumerate(items):
            results[idx] = fn(item)
            if on_progress:
                on_progress()
        return results

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {pool.submit(fn, item): idx for idx, item in enumerate(items)}
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
            if on_progress:
                on_progress() 

    return results

def _generate_and_validate(item: tuple, chapter_summary: str) -> tuple[dict, dict]:
    seg, bloom_level = item
    data = generate.generate_soal(seg, chapter_summary, bloom_level)
    stim_text = (data.get("stimulus") or {}).get("readable_text", "")
    result = validate.validate_soal(seg, data["question_text"], data["options"], data["correct_option"], stim_text)
    return data, result


LOTS_LEVELS = (1, 2, 3)
HOTS_LEVELS = (4, 5)


def _allocate(segments, hots_count, lots_count) -> list[tuple]:
    """Tiap segmen menghasilkan soal di SEMUA level dalam band-nya dulu (LOTS C1-C3, HOTS C4-C5)
    sebelum pindah ke segmen berikutnya -- satu segmen mencakup beberapa level kognitif, bukan
    satu segmen terkunci satu level. C6 (mencipta) di-drop -- MCQ 4 opsi tetap secara struktural
    tidak bisa menguji "create" murni, opsinya sudah ditulis lebih dulu oleh generator, bukan
    disusun siswa (lihat evaluasi Bloom-alignment)."""
    plan = _cross_product(segments, LOTS_LEVELS, lots_count)
    plan += _cross_product(segments, HOTS_LEVELS, hots_count)
    return plan


def _cross_product(segments, levels, count) -> list[tuple]:
    pairs = [(seg, level) for seg in segments for level in levels]
    return [pairs[i % len(pairs)] for i in range(count)]
