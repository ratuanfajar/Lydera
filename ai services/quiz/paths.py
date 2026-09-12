import sys
from pathlib import Path

QUIZ_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = QUIZ_DIR.parents[0] / "annotation"
BACKEND_DIR = QUIZ_DIR.parents[1] / "backend"


def setup() -> None:
    """Tambahkan folder quiz/, annotation/, dan backend/ ke sys.path, supaya impor datar
    (import config, import llm, import cache dari annotation/; import db dari backend/) bisa jalan."""
    for path in (QUIZ_DIR, ANNOTATION_DIR, BACKEND_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
