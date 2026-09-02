import json
import sys
from pathlib import Path

import db

READING_ORDER_STEP = 10


def create_module(conn, title) -> int:
    """Buat satu modul (buku) dan kembalikan id-nya."""
    cursor = conn.execute("INSERT INTO module (title) VALUES (?)", (title,))
    conn.commit()
    return int(cursor.lastrowid)


def create_chapter(conn, module_id, number=None, title=None, source_file=None) -> int:
    """Buat satu bab di bawah modul dan kembalikan id-nya."""
    cursor = conn.execute(
        "INSERT INTO chapter (module_id, number, title, source_file) VALUES (?, ?, ?, ?)",
        (module_id, number, title, source_file),
    )
    conn.commit()
    return int(cursor.lastrowid)


def ingest(conn, annotated_path, chapter_id) -> int:
    """Simpan blok annotated.json ke satu bab; append bertahap dalam bab yang sama."""
    blocks = json.loads(Path(annotated_path).read_text(encoding="utf-8"))
    base = current_max_order(conn, chapter_id)
    for offset, block in enumerate(blocks, start=1):
        conn.execute(
            """INSERT INTO block
                 (chapter_id, reading_order, block_type, readable_text, review_priority,
                  heading_level, source_markup, caption, image_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chapter_id, base + offset * READING_ORDER_STEP, block["block_type"],
             block["readable_text"], block.get("review_priority", "normal"),
             block.get("heading_level"), block.get("source_markup", ""),
             block.get("caption", ""), block.get("image_file", "")),
        )
    conn.commit()
    return len(blocks)


def current_max_order(conn, chapter_id) -> int:
    row = conn.execute("SELECT MAX(reading_order) AS m FROM block WHERE chapter_id = ?", (chapter_id,)).fetchone()
    return row["m"] or 0


if __name__ == "__main__":
    db.init_db()
    connection = db.connect()
    module_id = create_module(connection, sys.argv[2] if len(sys.argv) > 2 else "Modul")
    chapter_id = create_chapter(connection, module_id, source_file=sys.argv[1])
    count = ingest(connection, sys.argv[1], chapter_id)
    connection.close()
    print(f"[OK] module id={module_id}, chapter id={chapter_id}, {count} blok tersimpan")
