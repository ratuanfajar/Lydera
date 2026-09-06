from fastapi import APIRouter

import db
from app.schemas import FaseOut

router = APIRouter(prefix="/fase", tags=["fase"])


@router.get("", response_model=list[FaseOut])
def list_fase():
    conn = db.connect()
    try:
        rows = conn.execute("SELECT * FROM fase ORDER BY kode").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
