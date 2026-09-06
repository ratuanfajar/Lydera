import os
from pathlib import Path

from dotenv import load_dotenv

ANNOTATION_DIR = Path(__file__).parent
AI_SERVICE_DIR = ANNOTATION_DIR.parent

load_dotenv(AI_SERVICE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
MODEL = os.getenv("MODEL") or "qwen/qwen3.7-flash"
TEXT_MODEL = os.getenv("TEXT_MODEL") or MODEL
VISION_MODEL = os.getenv("VISION_MODEL") or MODEL
CACHE_DIR = Path(os.getenv("CACHE_DIR") or str(ANNOTATION_DIR / ".cache"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR") or str(ANNOTATION_DIR / "output"))
TEXT_MAX_TOKENS = int(os.getenv("TEXT_MAX_TOKENS") or "512")
VISION_MAX_TOKENS = int(os.getenv("VISION_MAX_TOKENS") or "1024")
LLM_MAX_WORKERS = int(os.getenv("LLM_MAX_WORKERS") or "4")
PROMPT_VERSION = "5"
