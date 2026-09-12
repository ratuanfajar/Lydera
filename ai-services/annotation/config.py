import os
from pathlib import Path

from dotenv import load_dotenv

ANNOTATION_DIR = Path(__file__).parent
AI_SERVICE_DIR = ANNOTATION_DIR.parent

load_dotenv(AI_SERVICE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL")

MODEL = "qwen/qwen3.7-flash"

TEXT_MODEL = MODEL
VISION_MODEL = MODEL
QUIZ_MODEL = "openai/gpt-4o"

CACHE_DIR = ANNOTATION_DIR / ".cache"
OUTPUT_DIR = ANNOTATION_DIR / "output"

TEXT_MAX_TOKENS = 512
VISION_MAX_TOKENS = 1024
LLM_MAX_WORKERS = 4

PROMPT_VERSION = "5"
