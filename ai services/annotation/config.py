import os
from pathlib import Path

from dotenv import load_dotenv

ANNOTATION_DIR = Path(__file__).parent
AI_SERVICE_DIR = ANNOTATION_DIR.parent

load_dotenv(AI_SERVICE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("LYDERA_MODEL", "qwen/qwen3.7-flash")
TEXT_MODEL = os.getenv("LYDERA_TEXT_MODEL", MODEL)
VISION_MODEL = os.getenv("LYDERA_VISION_MODEL", MODEL)
CACHE_DIR = Path(os.getenv("LYDERA_CACHE_DIR", str(ANNOTATION_DIR / ".cache")))
OUTPUT_DIR = Path(os.getenv("LYDERA_OUTPUT_DIR", str(ANNOTATION_DIR / "output")))
TEXT_MAX_TOKENS = int(os.getenv("LYDERA_TEXT_MAX_TOKENS", "512"))
VISION_MAX_TOKENS = int(os.getenv("LYDERA_VISION_MAX_TOKENS", "1024"))
MAX_WORKERS = int(os.getenv("LYDERA_MAX_WORKERS", "4"))
PROMPT_VERSION = "5"
