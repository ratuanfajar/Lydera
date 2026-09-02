import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "lydera.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None) -> None:
    conn = connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
