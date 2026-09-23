import sys
from pathlib import Path

CHATBOT_DIR = Path(__file__).resolve().parent
ANNOTATION_DIR = CHATBOT_DIR.parents[0] / "annotation"
QUIZ_DIR = CHATBOT_DIR.parents[0] / "quiz"
BACKEND_DIR = CHATBOT_DIR.parents[1] / "backend"


def setup() -> None:
    """Tambahkan folder chatbot/, annotation/, quiz/, dan backend/ ke sys.path"""
    for path in (CHATBOT_DIR, ANNOTATION_DIR, QUIZ_DIR, BACKEND_DIR):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
