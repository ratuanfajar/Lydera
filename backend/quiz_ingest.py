def create_quiz_request(conn, module_id) -> int:
    """Buat satu quiz_request dan kembalikan id-nya."""
    row = conn.execute(
        "INSERT INTO quiz_request (module_id) VALUES (%s) RETURNING id", (module_id,)
    ).fetchone()
    conn.commit()
    return row["id"]


def link_chapter(conn, quiz_request_id, chapter_id, hots_count, lots_count) -> None:
    """Kaitkan satu bab ke quiz_request dengan target jumlah soal LOTS/HOTS untuk bab itu."""
    conn.execute(
        """INSERT INTO quiz_request_chapter (quiz_request_id, chapter_id, hots_count, lots_count)
           VALUES (%s, %s, %s, %s)""",
        (quiz_request_id, chapter_id, hots_count, lots_count),
    )
    conn.commit()


def save_soal(conn, quiz_request_id, chapter_id, data, review_priority="normal", validation_notes=None) -> int:
    """Simpan satu soal hasil Generation+Validation (opsi, langkah, dan stimulus kalau ada) ke DB."""
    stimulus_id = None
    stimulus = data.get("stimulus")
    if stimulus:
        row = conn.execute(
            """INSERT INTO soal_stimulus
                 (quiz_request_id, chapter_id, source_markup, readable_text,
                  source_reading_order_start, source_reading_order_end)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (quiz_request_id, chapter_id, stimulus.get("source_markup", ""), stimulus["readable_text"],
             data["reading_order_start"], data["reading_order_end"]),
        ).fetchone()
        stimulus_id = row["id"]

    row = conn.execute(
        """INSERT INTO soal
             (quiz_request_id, chapter_id, stimulus_id, bloom_level, question_text, correct_option,
              kesimpulan, source_reading_order_start, source_reading_order_end,
              review_priority, validation_notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (quiz_request_id, chapter_id, stimulus_id, data["bloom_level"], data["question_text"],
         data["correct_option"], data["kesimpulan"], data["reading_order_start"], data["reading_order_end"],
         review_priority, validation_notes),
    ).fetchone()
    soal_id = row["id"]

    for label, opsi_text in data["options"].items():
        conn.execute(
            "INSERT INTO soal_opsi (soal_id, label, opsi_text) VALUES (%s, %s, %s)",
            (soal_id, label, opsi_text),
        )

    for urutan, teks in enumerate(data["langkah"], start=1):
        conn.execute(
            "INSERT INTO soal_langkah (soal_id, urutan, teks) VALUES (%s, %s, %s)",
            (soal_id, urutan, teks),
        )

    conn.commit()
    return soal_id
