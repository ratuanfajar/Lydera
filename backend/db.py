import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BACKEND_DIR = Path(__file__).parent
SCHEMA_PATH = BACKEND_DIR / "schema.sql"

load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/lydera"


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db() -> None:
    conn = connect()
    try:
        statements = [s.strip() for s in SCHEMA_PATH.read_text(encoding="utf-8").split(";") if s.strip()]
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
