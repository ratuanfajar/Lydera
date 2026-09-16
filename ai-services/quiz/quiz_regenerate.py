import revise
import segment as segment_module
import validate
from parallel import parallel_map


def _soal_content_equal(original: dict, data: dict) -> bool:
    """True kalau hasil revisi/recheck sama persis dengan soal aslinya -- dipakai supaya soal yang
    ternyata tidak terdampak (dikembalikan apa adanya) tidak ikut divalidasi ulang atau disentuh
    di DB (lihat `compute_regeneration`)."""
    return (
        original["question_text"] == data["question_text"]
        and original["options"] == data["options"]
        and original["correct_option"] == data["correct_option"]
        and original["langkah"] == data["langkah"]
        and original["kesimpulan"] == data["kesimpulan"]
    )


def compute_regeneration(chapter_id, all_blocks, reading_order_start, reading_order_end,
                          stimulus_text, target_soal: dict, sibling_soal: list[dict],
                          feedback: str) -> dict:
    """Edit satu soal yang dikritik guru (bukan generate ulang dari nol -- lihat `revise.py`).
    Kalau LLM menandai perubahan perlu sampai ke stimulus, stimulus direvisi lalu SEMUA soal di
    cluster (termasuk target) di-recheck paralel terhadap stimulus baru. Kalau tidak, cuma
    target_soal yang tersentuh -- stimulus dan soal lain di cluster sama sekali tidak diproses.

    Soal yang hasil recheck-nya identik dengan versi lama (tidak terdampak, `revise.py` diminta
    kembalikan apa adanya) di-skip total -- tidak divalidasi ulang, tidak masuk `soal_updates`,
    sehingga pemanggil (backend) tidak menyentuhnya sama sekali di DB. Ini penting terutama di
    jalur stimulus-berubah: dari beberapa soal yang berbagi satu stimulus, biasanya cuma sebagian
    yang benar-benar butuh penyesuaian konten.

    `target_soal`/`sibling_soal`: dict {id, question_text, options, correct_option, langkah,
    kesimpulan}, dibangun pemanggil dari ORM object/row DB. Return:
    {"new_stimulus_text": str|None, "soal_updates": [(soal_id, data, hasil_validasi), ...]} --
    new_stimulus_text None berarti stimulus tidak berubah.
    """
    seg_blocks = [b for b in all_blocks if reading_order_start <= b["reading_order"] <= reading_order_end]
    seg = segment_module.Segment(
        chapter_id=chapter_id,
        title="",
        reading_order_start=reading_order_start,
        reading_order_end=reading_order_end,
        text="\n".join(b["readable_text"] for b in seg_blocks),
    )

    edit = revise.revise_soal(seg, stimulus_text, target_soal, feedback)
    if not edit.get("needs_stimulus_change"):
        if _soal_content_equal(target_soal, edit):
            return {"new_stimulus_text": None, "soal_updates": []}
        val = validate.validate_soal(seg, edit["question_text"], edit["options"], edit["correct_option"], stimulus_text)
        return {"new_stimulus_text": None, "soal_updates": [(target_soal["id"], edit, val)]}

    # Stimulus perlu berubah -- revisi stimulus, lalu recheck SEMUA soal di cluster (termasuk
    # target) terhadap stimulus baru. Field soal dari `edit` di atas diabaikan sepenuhnya di sini
    # (walau LLM diminta tidak mengubahnya saat needs_stimulus_change=true, kita tidak bergantung
    # pada kepatuhan itu -- target diperlakukan identik dengan sibling, lewat recheck yang sama).
    new_stimulus_text = revise.revise_stimulus(seg, stimulus_text, feedback)
    all_soal = [target_soal] + sibling_soal
    rechecked = parallel_map(lambda s: revise.recheck_soal_for_new_stimulus(seg, new_stimulus_text, s), all_soal)
    updates = [
        (
            s["id"], data,
            validate.validate_soal(seg, data["question_text"], data["options"], data["correct_option"], new_stimulus_text),
        )
        for s, data in zip(all_soal, rechecked)
        if not _soal_content_equal(s, data)
    ]
    return {"new_stimulus_text": new_stimulus_text, "soal_updates": updates}


def regenerate_cluster(conn, soal_id, feedback) -> dict:
    """Versi psycopg (CLI/testing manual): baca soal + stimulus + cluster dari DB, lalu panggil
    `compute_regeneration`."""
    target_row = conn.execute("SELECT * FROM soal WHERE id = %s", (soal_id,)).fetchone()
    if target_row is None:
        raise ValueError(f"soal_id={soal_id} tidak ditemukan")
    if target_row["stimulus_id"] is None:
        raise ValueError(f"soal_id={soal_id} tidak punya stimulus")

    stimulus_id = target_row["stimulus_id"]
    stimulus = conn.execute("SELECT * FROM soal_stimulus WHERE id = %s", (stimulus_id,)).fetchone()
    if stimulus is None:
        raise ValueError(f"stimulus_id={stimulus_id} tidak ditemukan")

    cluster = conn.execute("SELECT * FROM soal WHERE stimulus_id = %s ORDER BY id", (stimulus_id,)).fetchall()

    def to_dict(soal_row) -> dict:
        opsi = conn.execute("SELECT label, opsi_text FROM soal_opsi WHERE soal_id = %s", (soal_row["id"],)).fetchall()
        langkah = conn.execute(
            "SELECT teks FROM soal_langkah WHERE soal_id = %s ORDER BY urutan", (soal_row["id"],)
        ).fetchall()
        return {
            "id": soal_row["id"],
            "question_text": soal_row["question_text"],
            "options": {o["label"]: o["opsi_text"] for o in opsi},
            "correct_option": soal_row["correct_option"],
            "langkah": [l["teks"] for l in langkah],
            "kesimpulan": soal_row["kesimpulan"],
        }

    target_soal = to_dict(target_row)
    sibling_soal = [to_dict(row) for row in cluster if row["id"] != soal_id]

    chapter_id = stimulus["chapter_id"]
    all_blocks = conn.execute(
        "SELECT reading_order, block_type, readable_text FROM block WHERE chapter_id = %s ORDER BY reading_order",
        (chapter_id,),
    ).fetchall()

    return compute_regeneration(
        chapter_id, all_blocks,
        stimulus["source_reading_order_start"], stimulus["source_reading_order_end"],
        stimulus["readable_text"], target_soal, sibling_soal, feedback,
    )
