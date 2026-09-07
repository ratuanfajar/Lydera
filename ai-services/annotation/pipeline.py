from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import annotate
import db
import ingest


def content_lists(outputs_dir: Path) -> list[Path]:
    found = [p for p in outputs_dir.rglob("*_content_list.json") if "content_list_v2" not in p.name]
    return sorted(found, key=_page_start)


def _page_start(path: Path) -> int:
    for part in path.parts:
        if part.startswith("p") and part[1:].split("-")[0].isdigit():
            return int(part[1:].split("-")[0])
    return 0


def run(conn, outputs_dir, chapter_id) -> int:
    """Annotate tiap window sebuah bab lalu ingest berurutan ke chapter tersebut."""
    total = 0
    for cl in content_lists(Path(outputs_dir)):
        blocks = annotate.annotate(cl)
        annotated_path = cl.parent / "annotated.json"
        annotated_path.write_text(
            json.dumps([asdict(b) for b in blocks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total += ingest.ingest(conn, annotated_path, chapter_id)
        print(f"[OK] {cl.parent.name}")
    return total


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Annotate + ingest semua window satu bab ke DB.")
    ap.add_argument("--outputs", required=True, help="folder output batch untuk satu bab")
    ap.add_argument("--module-id", type=int, default=None, help="id modul yang sudah ada")
    ap.add_argument("--module-title", default=None, help="judul modul baru bila --module-id tidak diberi")
    ap.add_argument("--chapter-number", type=int, default=None)
    ap.add_argument("--chapter-title", default=None)
    ap.add_argument("--source-file", default=None)
    ap.add_argument("--db", default=None)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    outputs = Path(args.outputs)
    if not outputs.exists():
        print(f"[ERROR] folder output tidak ada: {outputs}", file=sys.stderr)
        return 2

    db.init_db(args.db)
    conn = db.connect(args.db)
    try:
        module_id = args.module_id or ingest.create_module(conn, args.module_title or "Modul")
        chapter_id = ingest.create_chapter(
            conn, module_id, args.chapter_number, args.chapter_title, args.source_file
        )
        total = run(conn, outputs, chapter_id)
    finally:
        conn.close()
    print(f"[SELESAI] module id={module_id}, chapter id={chapter_id}, total {total} blok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
