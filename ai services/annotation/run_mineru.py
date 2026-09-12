from __future__ import annotations

import argparse
import os
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


def run(pdf: Path, out: Path, *, backend="pipeline", method="auto", lang=None,
        start=None, end=None, no_formula=False, no_table=False,
        device="auto", vram=None, keep_debug=False) -> int:
    """Jalankan MinerU sekali pada rentang halaman, in-process lewat `mineru.cli.common.do_parse`.

    Dulu ini `subprocess.run(["-m", "mineru.cli.client", ...])`, yang ternyata (dikonfirmasi
    langsung dari source mineru) menghidupkan lagi satu server FastAPI lokal per panggilan lewat
    subprocess kedua, cuma buat memproses satu window lalu dimatikan lagi -- artinya seluruh model
    MinerU (layout, OCR, formula, table) di-load ulang dari nol tiap window. `do_parse` adalah
    fungsi Python biasa yang dipakai server itu sendiri; model-nya di-cache sebagai singleton di
    dalam proses (lihat mineru/backend/pipeline/model_init.py -- `AtomModelSingleton`/
    `MineruPipelineModel` pakai `__new__` + dict `_models`), jadi selama dipanggil dari proses yang
    sama (annotation_worker.py, yang memang didesain long-running), window kedua dan seterusnya dalam satu bab
    -- bahkan bab berikutnya -- pakai model yang sudah ke-load, tidak reload lagi.
    """
    pdf = Path(pdf).resolve()
    out = Path(out).resolve()
    if not pdf.exists():
        print(f"[ERROR] PDF tidak ditemukan: {pdf}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)

    resolved = resolve_device(device)
    os.environ["MINERU_DEVICE_MODE"] = resolved
    if vram is not None:
        os.environ["MINERU_VIRTUAL_VRAM_SIZE"] = str(vram)
    if resolved.startswith("cuda") and not torch_sees_gpu():
        print("[WARN] CUDA diminta tapi torch tidak melihat GPU; proses jatuh ke CPU.", file=sys.stderr)

    try:
        from mineru.cli.common import do_parse, read_fn
    except ImportError:
        print("[ERROR] modul mineru tidak ditemukan. Jalankan lewat `uv run`.", file=sys.stderr)
        return 127

    print(f"[INFO] device : {resolved}")
    print(f"[INFO] jalan  : do_parse in-process pdf={pdf} out={out} halaman={start}-{end}")

    try:
        pdf_bytes = read_fn(pdf)
        do_parse(
            output_dir=str(out),
            pdf_file_names=[pdf.stem],
            pdf_bytes_list=[pdf_bytes],
            p_lang_list=[lang or "ch"],
            backend=backend,
            parse_method=method,
            formula_enable=not no_formula,
            table_enable=not no_table,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,
            f_dump_middle_json=False,
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=True,
            start_page_id=start if start is not None else 0,
            end_page_id=end,
        )
    except Exception as exc:
        print(f"[ERROR] MinerU gagal: {exc}", file=sys.stderr)
        return 1

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
