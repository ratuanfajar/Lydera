from fastapi import APIRouter, HTTPException

import db
import regenerate
from app.routers.quiz import _load_soal_out
from app.schemas import SoalEditRequest, SoalOut, SoalRegenerateRequest, SoalStatusResponse

router = APIRouter(prefix="/soal", tags=["soal"])


@router.get("/{soal_id}", response_model=SoalOut)
def get_soal(soal_id: int):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM soal WHERE id = %s", (soal_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "soal tidak ditemukan")
        return _load_soal_out(conn, row)
    finally:
        conn.close()


@router.patch("/{soal_id}", response_model=SoalOut)
def edit_soal(soal_id: int, payload: SoalEditRequest):
    """Edit langsung tanpa LLM. Cuma berlaku untuk soal berdiri sendiri (stimulus_id kosong, biasanya LOTS)."""
    conn = db.connect()
    try:
        soal = conn.execute("SELECT * FROM soal WHERE id = %s", (soal_id,)).fetchone()
        if soal is None:
            raise HTTPException(404, "soal tidak ditemukan")
        if soal["stimulus_id"] is not None:
            raise HTTPException(400, "soal ini punya stimulus, koreksi lewat POST /soal/{id}/regenerate")

        fields, values = [], []
        if payload.question_text is not None:
            fields.append("question_text = %s")
            values.append(payload.question_text)
        if payload.correct_option is not None:
            fields.append("correct_option = %s")
            values.append(payload.correct_option)
        if payload.kesimpulan is not None:
            fields.append("kesimpulan = %s")
            values.append(payload.kesimpulan)
        touched = bool(fields) or payload.options is not None or payload.langkah is not None
        if fields:
            conn.execute(f"UPDATE soal SET {', '.join(fields)} WHERE id = %s", (*values, soal_id))

        if payload.options is not None:
            conn.execute("DELETE FROM soal_opsi WHERE soal_id = %s", (soal_id,))
            for label, opsi_text in payload.options.items():
                conn.execute(
                    "INSERT INTO soal_opsi (soal_id, label, opsi_text) VALUES (%s, %s, %s)",
                    (soal_id, label, opsi_text),
                )

        if payload.langkah is not None:
            conn.execute("DELETE FROM soal_langkah WHERE soal_id = %s", (soal_id,))
            for urutan, teks in enumerate(payload.langkah, start=1):
                conn.execute(
                    "INSERT INTO soal_langkah (soal_id, urutan, teks) VALUES (%s, %s, %s)",
                    (soal_id, urutan, teks),
                )

        if touched:
            conn.execute("UPDATE soal SET review_status = 'edited' WHERE id = %s", (soal_id,))
        conn.commit()

        row = conn.execute("SELECT * FROM soal WHERE id = %s", (soal_id,)).fetchone()
        return _load_soal_out(conn, row)
    finally:
        conn.close()


@router.post("/{soal_id}/approve", response_model=SoalStatusResponse)
def approve_soal(soal_id: int):
    return _set_review_status(soal_id, "approved")


@router.post("/{soal_id}/reject", response_model=SoalStatusResponse)
def reject_soal(soal_id: int):
    return _set_review_status(soal_id, "rejected")


def _set_review_status(soal_id: int, status: str) -> dict:
    conn = db.connect()
    try:
        row = conn.execute("SELECT id FROM soal WHERE id = %s", (soal_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "soal tidak ditemukan")
        conn.execute("UPDATE soal SET review_status = %s WHERE id = %s", (status, soal_id))
        conn.commit()
    finally:
        conn.close()
    return {"id": soal_id, "review_status": status}


@router.post("/{soal_id}/regenerate", response_model=list[SoalOut])
def regenerate_soal(soal_id: int, payload: SoalRegenerateRequest):
    """Feedback guru memicu LLM regenerasi satu cluster HOTS penuh (soal ini + semua soal lain yang
    berbagi soal_stimulus yang sama). Guru approve draft hasilnya sebelum final -- review_status
    dikembalikan ke 'pending', bukan otomatis final."""
    conn = db.connect()
    try:
        soal = conn.execute("SELECT * FROM soal WHERE id = %s", (soal_id,)).fetchone()
        if soal is None:
            raise HTTPException(404, "soal tidak ditemukan")
        if soal["stimulus_id"] is None:
            raise HTTPException(400, "soal ini tidak punya stimulus, edit langsung lewat PATCH /soal/{id}")

        try:
            results = regenerate.regenerate_cluster(conn, soal["stimulus_id"], payload.feedback)
        except Exception as exc:
            raise HTTPException(502, f"regenerasi gagal, coba lagi: {exc}") from exc

        new_stimulus_text = (results[0][1].get("stimulus") or {}).get("readable_text", "")
        if new_stimulus_text:
            conn.execute(
                "UPDATE soal_stimulus SET readable_text = %s, review_status = 'edited' WHERE id = %s",
                (new_stimulus_text, soal["stimulus_id"]),
            )

        for updated_soal_id, data, val in results:
            review_priority = "normal" if val["matches"] else "high"
            validation_notes = None
            if not val["matches"]:
                validation_notes = (
                    f"Validasi independen sampai ke jawaban {val['derived_option']}, berbeda dari "
                    f"jawaban Generation ({data['correct_option']})."
                )
            conn.execute(
                """UPDATE soal SET question_text = %s, correct_option = %s, kesimpulan = %s,
                     review_status = 'pending', review_priority = %s, validation_notes = %s
                   WHERE id = %s""",
                (data["question_text"], data["correct_option"], data["kesimpulan"],
                 review_priority, validation_notes, updated_soal_id),
            )
            conn.execute("DELETE FROM soal_opsi WHERE soal_id = %s", (updated_soal_id,))
            for label, opsi_text in data["options"].items():
                conn.execute(
                    "INSERT INTO soal_opsi (soal_id, label, opsi_text) VALUES (%s, %s, %s)",
                    (updated_soal_id, label, opsi_text),
                )
            conn.execute("DELETE FROM soal_langkah WHERE soal_id = %s", (updated_soal_id,))
            for urutan, teks in enumerate(data["langkah"], start=1):
                conn.execute(
                    "INSERT INTO soal_langkah (soal_id, urutan, teks) VALUES (%s, %s, %s)",
                    (updated_soal_id, urutan, teks),
                )

        conn.commit()

        updated_rows = conn.execute(
            "SELECT * FROM soal WHERE stimulus_id = %s ORDER BY id", (soal["stimulus_id"],)
        ).fetchall()
        return [_load_soal_out(conn, r) for r in updated_rows]
    finally:
        conn.close()
