"""Proses worker quiz generator, terpisah dari proses Uvicorn."""
import traceback

import paths

paths.setup()

import time

import db
import quiz_pipeline

POLL_INTERVAL_SECONDS = 2


def run_worker_forever() -> None:
    while True:
        conn = db.connect()
        try:
            request = conn.execute(
                "SELECT id FROM quiz_request WHERE status = 'queued' ORDER BY id ASC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

        if request is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        _process(request["id"])


def _process(quiz_request_id) -> None:
    conn = db.connect()
    try:
        conn.execute("UPDATE quiz_request SET status='running', updated_at=now() WHERE id=%s", (quiz_request_id,))
        conn.commit()

        chapters = conn.execute(
            "SELECT chapter_id, hots_count, lots_count FROM quiz_request_chapter WHERE quiz_request_id = %s",
            (quiz_request_id,),
        ).fetchall()

        for ch in chapters:
            quiz_pipeline.run_for_chapter(conn, quiz_request_id, ch["chapter_id"], ch["hots_count"], ch["lots_count"])

        conn.execute("UPDATE quiz_request SET status='done', updated_at=now() WHERE id=%s", (quiz_request_id,))
        conn.commit()
    except Exception as exc:
        traceback.print_exc()
        conn.execute(
            "UPDATE quiz_request SET status='failed', error=%s, updated_at=now() WHERE id=%s",
            (str(exc), quiz_request_id),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    db.init_db()
    print("[INFO] worker quiz generator jalan, menunggu request di antrean...")
    run_worker_forever()
