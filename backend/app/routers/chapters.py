from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import config
import db
import ingest
import jobs
import pdf_cut
from app.schemas import ChapterCreateResponse, ChapterOut, JobStatus

router = APIRouter(prefix="/chapters", tags=["chapters"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


@router.post("", response_model=ChapterCreateResponse)
async def create_chapter(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...),
    module_id: int = Form(...),
    number: int | None = Form(None),
    title: str | None = Form(None),
    cp_id: int | None = Form(None),
):
    """Upload PDF modul + rentang halaman satu bab; potong PDF, buat bab, dan antrekan proses MinerU+anotasi."""
    if start_page < 0 or end_page < start_page:
        raise HTTPException(400, "rentang halaman tidak valid")

    conn = db.connect()
    try:
        module = conn.execute("SELECT fase_id FROM module WHERE id = %s", (module_id,)).fetchone()
        if module is None:
            raise HTTPException(404, "modul tidak ditemukan")

        if cp_id is not None:
            cp = conn.execute("SELECT fase_id FROM cp WHERE id = %s", (cp_id,)).fetchone()
            if cp is None:
                raise HTTPException(400, f"cp_id={cp_id} tidak ditemukan")
            if cp["fase_id"] != module["fase_id"]:
                raise HTTPException(400, "cp_id tidak sesuai fase modul ini")

        chapter_id = ingest.create_chapter(conn, module_id, number, title, file.filename, cp_id)

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = UPLOAD_DIR / f"raw-{chapter_id}.pdf"
        raw_path.write_bytes(await file.read())

        cut_path = UPLOAD_DIR / f"{chapter_id}.pdf"
        try:
            pdf_cut.cut(raw_path, cut_path, start_page, end_page)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            raw_path.unlink(missing_ok=True)

        out_dir = config.OUTPUT_DIR / str(chapter_id)
        if out_dir.exists() and any(out_dir.iterdir()):
            raise HTTPException(
                409, f"folder output {out_dir} sudah berisi data, tidak aman dipakai ulang"
            )
        job_id = jobs.enqueue(conn, chapter_id, cut_path, out_dir)
    finally:
        conn.close()

    return {"chapter_id": chapter_id, "job_id": job_id, "status": "queued"}


@router.get("/{chapter_id}", response_model=ChapterOut)
def get_chapter(chapter_id: int):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM chapter WHERE id = %s", (chapter_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, "bab tidak ditemukan")
    return dict(row)


@router.get("/{chapter_id}/status", response_model=JobStatus)
def get_status(chapter_id: int):
    conn = db.connect()
    try:
        job = jobs.get_latest_job_for_chapter(conn, chapter_id)
    finally:
        conn.close()
    if job is None:
        raise HTTPException(404, "belum ada proses untuk bab ini")
    return {
        "chapter_id": chapter_id,
        "job_id": job["id"],
        "status": job["status"],
        "error": job["error"],
        "blocks_total": job["blocks_total"],
    }
