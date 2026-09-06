from __future__ import annotations

import time
import traceback
from pathlib import Path

import paths

paths.setup()

import db
import batch
import pipeline
import run_mineru

POLL_INTERVAL_SECONDS = 2


def enqueue(conn, chapter_id, pdf_path, out_dir) -> int:
    """Masukkan satu job pemrosesan bab (MinerU + anotasi + ingest) ke antrean."""
    row = conn.execute(
        "INSERT INTO job (chapter_id, pdf_path, out_dir, status) VALUES (%s, %s, %s, 'queued') RETURNING id",
        (chapter_id, str(pdf_path), str(out_dir)),
    ).fetchone()
    conn.commit()
    return row["id"]


def get_latest_job_for_chapter(conn, chapter_id):
    return conn.execute(
        "SELECT * FROM job WHERE chapter_id = %s ORDER BY id DESC LIMIT 1", (chapter_id,)
    ).fetchone()


def run_worker_forever() -> None:
    """Entry point untuk proses worker MinerU yang berdiri sendiri (lihat worker.py).

    Selalu dijalankan sebagai proses terpisah dari API (bukan thread di dalam
    proses FastAPI), supaya jumlahnya tetap tepat satu tidak peduli berapa
    banyak proses Uvicorn yang melayani HTTP.
    """
    _worker_loop()


def _worker_loop() -> None:
    while True:
        conn = db.connect()
        try:
            job = conn.execute(
                "SELECT * FROM job WHERE status = 'queued' ORDER BY id ASC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        _process(job["id"], job["pdf_path"], job["out_dir"], job["chapter_id"])


def _process(job_id, pdf_path, out_dir, chapter_id) -> None:
    conn = db.connect()
    try:
        _mark(conn, job_id, "running")
        windows = batch.plan(Path(pdf_path), Path(out_dir), batch.DEFAULT_MAX_PAGES)
        for w in windows:
            rc = run_mineru.run(pdf_path, w.out_dir, start=w.start_page, end=w.end_page)
            if rc != 0:
                raise RuntimeError(f"MinerU gagal pada window {w.label}")
        total = pipeline.run(conn, out_dir, chapter_id)
        _mark(conn, job_id, "done", blocks_total=total)
    except Exception as exc:
        traceback.print_exc()
        _mark(conn, job_id, "failed", error=str(exc))
    finally:
        conn.close()


def _mark(conn, job_id, status, *, error=None, blocks_total=None) -> None:
    conn.execute(
        """UPDATE job SET status = %s, error = %s,
             blocks_total = COALESCE(%s, blocks_total),
             updated_at = now()
           WHERE id = %s""",
        (status, error, blocks_total, job_id),
    )
    conn.commit()
