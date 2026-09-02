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


def run(outputs_dir, source_file, db_path=None) -> tuple[int | None, int]:
    """Annotate tiap window sebuah modul lalu ingest berurutan ke satu module di DB."""
    db.init_db(db_path)
    conn = db.connect(db_path)
    module_id, total = None, 0
    try:
        for cl in content_lists(Path(outputs_dir)):
            blocks = annotate.annotate(cl)
            annotated_path = cl.parent / "annotated.json"
            annotated_path.write_text(
                json.dumps([asdict(b) for b in blocks], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            module_id, count = ingest.ingest(conn, annotated_path, source_file)
            total += count
            print(f"[OK] {cl.parent.name}: {count} blok")
    finally:
        conn.close()
    return module_id, total


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Annotate + ingest semua window MinerU sebuah modul ke DB.")
    ap.add_argument("--outputs", required=True, help="folder output batch modul (berisi window p####-####)")
    ap.add_argument("--source-file", required=True, help="nama file PDF asli untuk identitas module")
    ap.add_argument("--db", default=None)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    outputs = Path(args.outputs)
    if not outputs.exists():
        print(f"[ERROR] folder output tidak ada: {outputs}", file=sys.stderr)
        return 2
    module_id, total = run(outputs, args.source_file, args.db)
    if module_id is None:
        print("[WARN] tidak ada content_list untuk diproses", file=sys.stderr)
        return 1
    print(f"[SELESAI] module id={module_id}, total {total} blok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
