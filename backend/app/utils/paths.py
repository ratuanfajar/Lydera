import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ANNOTATION_DIR = BACKEND_DIR.parent / "ai-services" / "annotation"


def setup() -> None:
    """Tambahkan folder backend dan layanan AI ke sys.path untuk impor datar (import db, import config, dst)."""
    for path in (BACKEND_DIR, ANNOTATION_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
