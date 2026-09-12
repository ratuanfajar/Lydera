from fastapi import APIRouter, HTTPException

import annotation_ingest
import db
from app.schemas import CpOut, ModuleCreate, ModuleOut

router = APIRouter(prefix="/modules", tags=["modules"])


@router.post("", response_model=ModuleOut)
def create_module(payload: ModuleCreate):
    conn = db.connect()
    try:
        fase = conn.execute("SELECT id FROM fase WHERE id = %s", (payload.fase_id,)).fetchone()
        if fase is None:
            raise HTTPException(400, f"fase_id={payload.fase_id} tidak ditemukan")
        module_id = annotation_ingest.create_module(conn, payload.title, payload.fase_id)
        row = conn.execute("SELECT * FROM module WHERE id = %s", (module_id,)).fetchone()
    finally:
        conn.close()
    return dict(row)


@router.get("", response_model=list[ModuleOut])
def list_modules():
    conn = db.connect()
    try:
        rows = conn.execute("SELECT * FROM module ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{module_id}/cp", response_model=list[CpOut])
def list_module_cp(module_id: int):
    """Daftar domain CP yang sesuai fase modul ini, untuk dipilih guru saat upload bab."""
    conn = db.connect()
    try:
        module = conn.execute("SELECT fase_id FROM module WHERE id = %s", (module_id,)).fetchone()
        if module is None:
            raise HTTPException(404, "modul tidak ditemukan")
        if module["fase_id"] is None:
            return []
        rows = conn.execute(
            "SELECT * FROM cp WHERE fase_id = %s ORDER BY domain", (module["fase_id"],)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
