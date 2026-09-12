from fastapi import APIRouter, HTTPException

import db
import quiz_ingest
from app.schemas import (
    QuizRequestCreate,
    QuizRequestCreateResponse,
    QuizRequestStatus,
    SoalOpsiOut,
    SoalOut,
)

router = APIRouter(tags=["quiz"])


@router.post("/quiz-requests", response_model=QuizRequestCreateResponse)
def create_quiz_request(payload: QuizRequestCreate):
    """Buat request generate quiz untuk satu atau lebih bab dalam satu modul. Diproses async oleh quiz_worker.py."""
    if not payload.chapters:
        raise HTTPException(400, "chapters tidak boleh kosong")

    conn = db.connect()
    try:
        module = conn.execute("SELECT id FROM module WHERE id = %s", (payload.module_id,)).fetchone()
        if module is None:
            raise HTTPException(404, "modul tidak ditemukan")

        for item in payload.chapters:
            chapter = conn.execute(
                "SELECT module_id FROM chapter WHERE id = %s", (item.chapter_id,)
            ).fetchone()
            if chapter is None:
                raise HTTPException(404, f"chapter_id={item.chapter_id} tidak ditemukan")
            if chapter["module_id"] != payload.module_id:
                raise HTTPException(400, f"chapter_id={item.chapter_id} bukan bagian dari modul ini")

        quiz_request_id = quiz_ingest.create_quiz_request(conn, payload.module_id)
        for item in payload.chapters:
            quiz_ingest.link_chapter(conn, quiz_request_id, item.chapter_id, item.hots_count, item.lots_count)
    finally:
        conn.close()

    return {"quiz_request_id": quiz_request_id, "status": "queued"}


@router.get("/quiz-requests/{quiz_request_id}/status", response_model=QuizRequestStatus)
def get_quiz_request_status(quiz_request_id: int):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT status, error FROM quiz_request WHERE id = %s", (quiz_request_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, "quiz_request tidak ditemukan")
    return {"quiz_request_id": quiz_request_id, "status": row["status"], "error": row["error"]}


@router.get("/quiz-requests/{quiz_request_id}/soal", response_model=list[SoalOut])
def list_soal_for_request(quiz_request_id: int):
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM soal WHERE quiz_request_id = %s ORDER BY id", (quiz_request_id,)
        ).fetchall()
        return [_load_soal_out(conn, row) for row in rows]
    finally:
        conn.close()


def _load_soal_out(conn, soal_row) -> dict:
    opsi_rows = conn.execute(
        "SELECT label, opsi_text FROM soal_opsi WHERE soal_id = %s ORDER BY label", (soal_row["id"],)
    ).fetchall()
    langkah_rows = conn.execute(
        "SELECT teks FROM soal_langkah WHERE soal_id = %s ORDER BY urutan", (soal_row["id"],)
    ).fetchall()
    stimulus_text = None
    if soal_row["stimulus_id"] is not None:
        stimulus = conn.execute(
            "SELECT readable_text FROM soal_stimulus WHERE id = %s", (soal_row["stimulus_id"],)
        ).fetchone()
        stimulus_text = stimulus["readable_text"] if stimulus else None

    return {
        "id": soal_row["id"],
        "chapter_id": soal_row["chapter_id"],
        "stimulus_id": soal_row["stimulus_id"],
        "bloom_level": soal_row["bloom_level"],
        "question_text": soal_row["question_text"],
        "options": [SoalOpsiOut(**dict(r)) for r in opsi_rows],
        "correct_option": soal_row["correct_option"],
        "langkah": [r["teks"] for r in langkah_rows],
        "kesimpulan": soal_row["kesimpulan"],
        "stimulus_text": stimulus_text,
        "review_status": soal_row["review_status"],
        "review_priority": soal_row["review_priority"],
        "validation_notes": soal_row["validation_notes"],
    }
