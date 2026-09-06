from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

import db
import jobs
import regenerate
from app.schemas import BlockOut, RegenerateRequest, RegenerateResponse

router = APIRouter(tags=["blocks"])


@router.get("/chapters/{chapter_id}/blocks", response_model=list[BlockOut])
def list_blocks(chapter_id: int):
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM block WHERE chapter_id = %s ORDER BY reading_order", (chapter_id,)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/blocks/{block_id}/regenerate", response_model=RegenerateResponse)
def regenerate_block(block_id: int, payload: RegenerateRequest):
    conn = db.connect()
    try:
        block = conn.execute("SELECT * FROM block WHERE id = %s", (block_id,)).fetchone()
        if block is None:
            raise HTTPException(404, "blok tidak ditemukan")
        if block["block_type"] not in ("formula", "table", "image"):
            raise HTTPException(400, f"regenerasi tidak berlaku untuk block_type={block['block_type']}")

        image_path = None
        if block["image_file"]:
            job = jobs.get_latest_job_for_chapter(conn, block["chapter_id"])
            if job is not None:
                image_path = _find_image(Path(job["out_dir"]), block["image_file"])

        new_text = regenerate.regenerate(
            block["block_type"], payload.feedback,
            source_markup=block["source_markup"] or "",
            image_path=image_path,
            caption=block["caption"] or "",
        )
        conn.execute("UPDATE block SET readable_text = %s WHERE id = %s", (new_text, block_id))
        conn.commit()
    finally:
        conn.close()
    return {"block_id": block_id, "readable_text": new_text}


def _find_image(out_dir: Path, image_file: str) -> Path | None:
    if not out_dir.exists():
        return None
    matches = list(out_dir.rglob(image_file))
    return matches[0] if matches else None
