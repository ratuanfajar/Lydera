from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

import config
import run_mineru

DEFAULT_MAX_PAGES = 3


@dataclass
class Window:
    label: str
    start_page: int
    end_page: int
    out_dir: Path


def plan(pdf: Path, base_out: Path, max_pages: int) -> list[Window]:
    """Pecah seluruh PDF (sudah terfokus dari BE) jadi window MinerU per --max-pages."""
    last = len(PdfReader(str(pdf)).pages) - 1
    windows: list[Window] = []
    for s, e in _windows(0, last, max_pages):
        windows.append(Window(f"hlm {s}-{e}", s, e, base_out / f"p{s:04d}-{e:04d}"))
    return windows


def _windows(start: int, end: int, max_pages: int) -> list[tuple[int, int]]:
    if max_pages <= 0:
        return [(start, end)]
    return [(s, min(s + max_pages - 1, end)) for s in range(start, end + 1, max_pages)]


def run_window(pdf: Path, window: Window, args: argparse.Namespace) -> int:
    return run_mineru.run(
        pdf, window.out_dir,
        method=args.method, start=window.start_page, end=window.end_page,
        no_formula=args.no_formula, no_table=args.no_table,
        device=args.device, vram=args.vram,
    )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Proses seluruh PDF modul (terfokus) per window MinerU.")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=str(config.OUTPUT_DIR))
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    ap.add_argument("--method", default="auto", choices=["auto", "txt", "ocr"])
    ap.add_argument("--no-formula", action="store_true")
    ap.add_argument("--no-table", action="store_true")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--vram", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    pdf = Path(args.pdf).resolve()
    if not pdf.exists():
        print(f"[ERROR] PDF tidak ditemukan: {pdf}", file=sys.stderr)
        return 2

    windows = plan(pdf, Path(args.out).resolve(), args.max_pages)
    print(f"[INFO] {len(windows)} window (max_pages={args.max_pages}):")
    for w in windows:
        print(f"   {w.label:16} -> {w.out_dir}")
    if args.dry_run:
        print("[OK] dry-run, tidak menjalankan MinerU")
        return 0

    failed = []
    for i, w in enumerate(windows, start=1):
        print(f"\n[RUN {i}/{len(windows)}] {w.label}")
        if run_window(pdf, w, args) != 0:
            failed.append(w.label)
            print(f"[ERROR] gagal: {w.label}", file=sys.stderr)

    print(f"\n[SELESAI] sukses {len(windows) - len(failed)}/{len(windows)}")
    if failed:
        print("[GAGAL] " + "; ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
