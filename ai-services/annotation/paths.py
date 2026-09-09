import sys
from pathlib import Path

ANNOTATION_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ANNOTATION_DIR.parents[1] / "backend"


def setup() -> None:
    """Tambahkan folder layanan AI dan backend ke sys.path untuk impor datar (import config, import db, dst)."""
    for path in (ANNOTATION_DIR, BACKEND_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
