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
PROMPT_VERSION = "12"
FORMULA_PROMPT_VERSION = "2"
TABLE_PROMPT_VERSION = "4"
TABLE_MAX_TOKENS = 4000

EMBEDDING_API_KEY = (os.getenv("EMBEDDING_API_KEY") or AZURE_OPENAI_API_KEY).strip()
EMBEDDING_BASE_URL = (os.getenv("EMBEDDING_BASE_URL") or AZURE_OPENAI_BASE_URL or "").strip() or None
EMBEDDING_MODEL = (os.getenv("EMBEDDING_MODEL") or "text-embedding-3-large").strip()
EMBEDDING_BATCH_SIZE = 16
EMBEDDING_MAX_WORKERS = 6
EMBEDDING_DIM = int((os.getenv("EMBEDDING_DIM") or "3072").strip())
