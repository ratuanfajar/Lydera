from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
import annotate

def content_lists(outputs_dir: Path) -> list[Path]:
    found = [p for p in outputs_dir.rglob("*_content_list.json") if "content_list_v2" not in p.name]
    return sorted(found, key=_page_start)


def _page_start(path: Path) -> int:
    for part in path.parts:
        if part.startswith("p") and part[1:].split("-")[0].isdigit():
            return int(part[1:].split("-")[0])
    return 0

def run(outputs_dir) -> list[Path]:
    """Annotate tiap window sebuah bab dan kembalikan list file JSON yang dihasilkan."""
    annotated_files = []
    
    for cl in content_lists(Path(outputs_dir)):
        blocks = annotate.annotate(cl)
        annotated_path = cl.parent / "annotated.json"
        
        annotated_path.write_text(
            json.dumps([asdict(b) for b in blocks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        annotated_files.append(annotated_path)
        print(f"[OK] {cl.parent.name}")
        
    return annotated_files

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Annotate semua window satu bab (tanpa ingest ke DB).")
    ap.add_argument("--outputs", required=True, help="folder output batch untuk satu bab")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    outputs = Path(args.outputs)
    
    if not outputs.exists():
        print(f"[ERROR] folder output tidak ada: {outputs}", file=sys.stderr)
        return 2

    # Hanya jalankan AI, tidak ada lagi logika create_module atau create_chapter di sini!
    print(f"[INFO] Mulai memproses anotasi untuk {outputs}...")
    hasil_json = run(outputs)
    
    print(f"[SELESAI] Total {len(hasil_json)} file JSON berhasil digenerate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())