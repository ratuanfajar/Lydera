from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from annoter import annotate, config
from annoter.resilience import Breaker

logger = logging.getLogger("annoter")


class AnnotationFailure(RuntimeError):
    pass


@dataclass
class RunReport:
    paths: list[Path]
    failed_windows: list[str]
    failed_blocks: int
    attempted: int

    @property
    def needs_review(self) -> int:
        return self.failed_blocks + len(self.failed_windows)


def content_lists(outputs_dir: Path) -> list[Path]:
    found = [p for p in outputs_dir.rglob("*_content_list.json") if "content_list_v2" not in p.name]
    return sorted(found, key=_page_start)


def run(outputs_dir) -> list[Path]:
    """Annotate tiap window dan kembalikan file JSON yang berhasil; error bila gagal melewati ambang."""
    return run_with_report(outputs_dir).paths


def run_with_report(outputs_dir) -> RunReport:
    """Seperti run, tetapi mengembalikan juga jumlah window dan blok yang gagal."""
    breaker = Breaker(config.BREAKER_THRESHOLD)
    report = RunReport([], [], 0, 0)
    for content_list in content_lists(Path(outputs_dir)):
        _annotate_window(content_list, breaker, report)
        if breaker.tripped:
            raise AnnotationFailure(f"layanan LLM tidak tersedia; pemrosesan dihentikan setelah window {content_list.parent.name}")
    ensure_reliable(report)
    return report


def ensure_reliable(report: RunReport) -> None:
    windows = len(report.paths) + len(report.failed_windows)
    if report.failed_windows and len(report.failed_windows) / windows > config.MAX_FAILURE_RATIO:
        raise AnnotationFailure(f"{len(report.failed_windows)} dari {windows} window gagal: {', '.join(report.failed_windows)}")
    if report.attempted and report.failed_blocks / report.attempted > config.MAX_FAILURE_RATIO:
        raise AnnotationFailure(f"{report.failed_blocks} dari {report.attempted} blok berpanggilan LLM gagal")
    if report.needs_review:
        logger.warning("window gagal: %s; blok gagal: %s dari %s", report.failed_windows or "-", report.failed_blocks, report.attempted)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    outputs = Path(args.outputs)
    if not outputs.exists():
        print(f"[ERROR] folder output tidak ada: {outputs}", file=sys.stderr)
        return 2
    print(f"[INFO] Mulai memproses anotasi untuk {outputs}...")
    paths = run(outputs)
    print(f"[SELESAI] Total {len(paths)} file JSON berhasil digenerate.")
    return 0


def _annotate_window(content_list: Path, breaker: Breaker, report: RunReport) -> None:
    window = content_list.parent.name
    try:
        result = annotate.annotate_window(content_list, breaker)
        path = content_list.parent / "annotated.json"
        path.write_text(json.dumps([asdict(block) for block in result.blocks], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as error:
        logger.error("%s gagal: %s: %s", window, type(error).__name__, error)
        report.failed_windows.append(window)
        return
    report.paths.append(path)
    report.failed_blocks += result.failed
    report.attempted += result.attempted
    logger.info("%s selesai", window)


def _page_start(path: Path) -> int:
    for part in path.parts:
        if part.startswith("p") and part[1:].split("-")[0].isdigit():
            return int(part[1:].split("-")[0])
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate semua window satu bab (tanpa ingest ke DB).")
    parser.add_argument("--outputs", required=True, help="folder output batch untuk satu bab")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
