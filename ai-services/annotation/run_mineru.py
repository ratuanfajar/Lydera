from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import config

DEBUG_SUFFIXES = (
    "_content_list_v2.json",
    "_middle.json",
    "_model.json",
    "_layout.pdf",
    "_span.pdf",
    "_origin.pdf",
)


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return "cuda" if torch_sees_gpu() else "cpu"


def torch_sees_gpu() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def build_command(pdf: Path, out: Path, *, backend: str, method: str, lang: str | None,
                  start: int | None, end: int | None, no_formula: bool, no_table: bool) -> list[str]:
    cmd = [
        sys.executable, "-m", "mineru.cli.client",
        "-p", str(pdf),
        "-o", str(out),
        "-b", backend,
        "-m", method,
        "-f", "false" if no_formula else "true",
        "-t", "false" if no_table else "true",
    ]
    if lang:
        cmd += ["-l", lang]
    if start is not None:
        cmd += ["-s", str(start)]
    if end is not None:
        cmd += ["-e", str(end)]
    return cmd


def run(pdf: Path, out: Path, *, backend="pipeline", method="auto", lang=None,
        start=None, end=None, no_formula=False, no_table=False,
        device="auto", vram=None, keep_debug=False) -> int:
    """Jalankan MinerU sekali pada rentang halaman; bersihkan file debug; kembalikan return code."""
    pdf = Path(pdf).resolve()
    out = Path(out).resolve()
    if not pdf.exists():
        print(f"[ERROR] PDF tidak ditemukan: {pdf}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    resolved = resolve_device(device)
    env = os.environ.copy()
    env["MINERU_DEVICE_MODE"] = resolved
    if vram is not None:
        env["MINERU_VIRTUAL_VRAM_SIZE"] = str(vram)
    if resolved.startswith("cuda") and not torch_sees_gpu():
        print("[WARN] CUDA diminta tapi torch tidak melihat GPU; proses jatuh ke CPU.", file=sys.stderr)

    cmd = build_command(pdf, out, backend=backend, method=method, lang=lang,
                        start=start, end=end, no_formula=no_formula, no_table=no_table)
    print(f"[INFO] device : {resolved}")
    print(f"[INFO] jalan  : {' '.join(cmd)}")

    try:
        proc = subprocess.run(cmd, env=env)
    except FileNotFoundError:
        print("[ERROR] modul mineru tidak ditemukan. Jalankan lewat `uv run`.", file=sys.stderr)
        return 127
    if proc.returncode != 0:
        print(f"[ERROR] MinerU keluar dengan kode {proc.returncode}", file=sys.stderr)
        return proc.returncode

    if not keep_debug:
        removed = remove_debug_files(out, pdf.stem)
        if removed:
            print(f"[INFO] file debug dihapus: {len(removed)}")
    for key, paths in find_kept_outputs(out, pdf.stem).items():
        target = paths[0] if paths else None
        print(f"[OK] {key}: {target if target else '(tidak ditemukan)'}")
    return 0


def remove_debug_files(out: Path, pdf_stem: str) -> list[str]:
    removed = []
    for path in out.rglob(f"{pdf_stem}*"):
        if path.is_file() and any(path.name.endswith(sfx) for sfx in DEBUG_SUFFIXES):
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed


def find_kept_outputs(out: Path, pdf_stem: str) -> dict[str, list[Path]]:
    return {
        "content_list": [p for p in out.rglob(f"{pdf_stem}*content_list.json")
                         if "content_list_v2" not in p.name],
        "markdown": list(out.rglob(f"{pdf_stem}*.md")),
        "images": [p for p in out.rglob("images") if p.is_dir()],
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Jalankan MinerU pada satu PDF modul.")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=str(config.OUTPUT_DIR))
    ap.add_argument("--backend", default="pipeline")
    ap.add_argument("--method", default="auto", choices=["auto", "txt", "ocr"])
    ap.add_argument("--lang", default=None)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--no-formula", action="store_true")
    ap.add_argument("--no-table", action="store_true")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--vram", type=int, default=None)
    ap.add_argument("--keep-debug", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    return run(args.pdf, args.out, backend=args.backend, method=args.method, lang=args.lang,
               start=args.start, end=args.end, no_formula=args.no_formula, no_table=args.no_table,
               device=args.device, vram=args.vram, keep_debug=args.keep_debug)


if __name__ == "__main__":
    raise SystemExit(main())
