import json
import sys
from pathlib import Path

import db

READING_ORDER_STEP = 10


def ingest(conn, annotated_path, source_file) -> tuple[int, int]:
    """Simpan blok annotated.json ke DB; append bertahap ke modul yang sama."""
    blocks = json.loads(Path(annotated_path).read_text(encoding="utf-8"))
    module_id = find_or_create_module(conn, module_meta(source_file))
    base = current_max_order(conn, module_id)
    for offset, block in enumerate(blocks, start=1):
        conn.execute(
            """INSERT INTO block
                 (module_id, reading_order, block_type, readable_text, review_priority,
                  heading_level, source_markup, caption, image_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (module_id, base + offset * READING_ORDER_STEP, block["block_type"],
             block["readable_text"], block.get("review_priority", "normal"),
             block.get("heading_level"), block.get("source_markup", ""),
             block.get("caption", ""), block.get("image_file", "")),
        )
    conn.commit()
    return module_id, len(blocks)


def module_meta(source_file) -> dict:
    return {"source_file": Path(source_file).name, "title": Path(source_file).stem}


def find_or_create_module(conn, meta) -> int:
    row = conn.execute("SELECT id FROM module WHERE source_file = ?", (meta["source_file"],)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO module (source_file, title) VALUES (?, ?)",
        (meta["source_file"], meta["title"]),
    )
    return int(cursor.lastrowid)


def current_max_order(conn, module_id) -> int:
    row = conn.execute("SELECT MAX(reading_order) AS m FROM block WHERE module_id = ?", (module_id,)).fetchone()
    return row["m"] or 0


if __name__ == "__main__":
    db.init_db()
    connection = db.connect()
    module_id, count = ingest(connection, sys.argv[1], sys.argv[2])
    connection.close()
    print(f"[OK] modul id={module_id}, {count} blok tersimpan")
