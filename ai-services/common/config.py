import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

AI_SERVICE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(AI_SERVICE_DIR / ".env")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
_endpoint = urlparse(os.getenv("AZURE_OPENAI_ENDPOINT", "").strip())
AZURE_OPENAI_BASE_URL = f"{_endpoint.scheme}://{_endpoint.netloc}/openai/v1/" if _endpoint.netloc else None

TEXT_MODEL = "gpt-5.4-mini"
VISION_MODEL = "gpt-5.4-mini"

TEXT_EFFORT = "none"
VISION_EFFORT = "none"
REASONING_EFFORT = "low"

TEXT_MAX_TOKENS = 512
VISION_MAX_TOKENS = 1800
LLM_MAX_WORKERS = 4

CACHE_DIR = AI_SERVICE_DIR / ".cache"
PROMPT_VERSION = "6"
