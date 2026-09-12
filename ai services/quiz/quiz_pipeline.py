from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import paths

paths.setup()

import config
import context
import db
import generate
import quiz_ingest
import segment
import validate


def run_for_chapter(conn, quiz_request_id, chapter_id, hots_count, lots_count) -> int:
    """Jalankan Chain 0-4 untuk satu bab, simpan hasilnya ke DB. Mengembalikan jumlah soal tersimpan.

    Map (ringkas tiap segmen) dan Generation+Validation (tiap soal) dijalankan paralel -- keduanya
    independen satu sama lain dalam satu bab (segmen tidak saling butuh; soal cuma butuh segmen +
    chapter_summary yang sudah pasti selesai lebih dulu). Reduce tetap satu panggilan tunggal
    (butuh semua ringkasan Map bab ini). Penulisan ke DB tetap satu-satu di thread utama karena satu
    koneksi psycopg tidak aman dipakai bersamaan dari banyak thread.
    """
    blocks = conn.execute(
        "SELECT reading_order, block_type, readable_text FROM block WHERE chapter_id = %s ORDER BY reading_order",
        (chapter_id,),
    ).fetchall()
    segments = segment.build_segments(chapter_id, blocks)
    if not segments:
        raise RuntimeError(f"chapter {chapter_id}: tidak ada sub-bab berpola 'A. ...' untuk dijadikan soal")

    summaries = _parallel_map(context.summarize_segment, segments)
    chapter_summary = context.summarize_chapter(summaries)

    plan = _allocate(segments, hots_count, lots_count)
    computed = _parallel_map(lambda item: _generate_and_validate(item, chapter_summary), plan)

    saved = 0
    for data, result in computed:
        review_priority = "normal" if result["matches"] else "high"
        validation_notes = None
        if not result["matches"]:
            validation_notes = (
                f"Validasi independen sampai ke jawaban {result['derived_option']}, berbeda dari "
                f"jawaban Generation ({data['correct_option']}). Langkah validasi: "
                f"{'; '.join(result['derived_langkah'])}"
            )

        quiz_ingest.save_soal(conn, quiz_request_id, chapter_id, data, review_priority, validation_notes)
        saved += 1
    return saved


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


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Jalankan quiz generator (Chain 0-4) untuk satu bab.")
    ap.add_argument("--quiz-request-id", type=int, default=None, help="quiz_request yang sudah ada")
    ap.add_argument("--chapter-id", type=int, required=True)
    ap.add_argument("--hots", type=int, default=0)
    ap.add_argument("--lots", type=int, default=0)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = db.connect()
    quiz_request_id = args.quiz_request_id
    try:
        if quiz_request_id is None:
            module_id = conn.execute(
                "SELECT module_id FROM chapter WHERE id = %s", (args.chapter_id,)
            ).fetchone()["module_id"]
            quiz_request_id = quiz_ingest.create_quiz_request(conn, module_id)
            quiz_ingest.link_chapter(conn, quiz_request_id, args.chapter_id, args.hots, args.lots)
            print(f"[INFO] quiz_request_id baru dibuat: {quiz_request_id}")

        conn.execute("UPDATE quiz_request SET status='running', updated_at=now() WHERE id=%s", (quiz_request_id,))
        conn.commit()
        try:
            saved = run_for_chapter(conn, quiz_request_id, args.chapter_id, args.hots, args.lots)
        except Exception as exc:
            conn.execute(
                "UPDATE quiz_request SET status='failed', error=%s, updated_at=now() WHERE id=%s",
                (str(exc), quiz_request_id),
            )
            conn.commit()
            raise
        conn.execute("UPDATE quiz_request SET status='done', updated_at=now() WHERE id=%s", (quiz_request_id,))
        conn.commit()
    finally:
        conn.close()
    print(f"[SELESAI] {saved} soal tersimpan, chapter_id={args.chapter_id}, quiz_request_id={quiz_request_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
