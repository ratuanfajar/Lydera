import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ANNOTATION_DIR = Path(__file__).parent
AI_SERVICE_DIR = ANNOTATION_DIR.parent

load_dotenv(AI_SERVICE_DIR / ".env")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
_endpoint = urlparse(os.getenv("AZURE_OPENAI_ENDPOINT", "").strip())
AZURE_OPENAI_BASE_URL = f"{_endpoint.scheme}://{_endpoint.netloc}/openai/v1/" if _endpoint.netloc else None

TEXT_MODEL = "gpt-5.4-mini"
VISION_MODEL = "gpt-5.4-mini"
QUIZ_MODEL = "gpt-5.4-mini"
QUIZ_VALIDATOR_MODEL = "grok-4.3"

TEXT_EFFORT = "none"
VISION_EFFORT = "none"
REASONING_EFFORT = "low"

CACHE_DIR = ANNOTATION_DIR / ".cache"
OUTPUT_DIR = ANNOTATION_DIR / "output"

TEXT_MAX_TOKENS = 512
VISION_MAX_TOKENS = 1800
LLM_MAX_WORKERS = 4

PROMPT_VERSION = "6"

# --- Chatbot (RAG) ---
CHAT_MODEL = (os.getenv("CHAT_MODEL") or "gpt-5.4-mini").strip()
CHAT_MAX_TOKENS = int((os.getenv("CHAT_MAX_TOKENS") or "1024").strip())
MAX_TOOL_ITERATIONS = int((os.getenv("MAX_TOOL_ITERATIONS") or "10").strip())
TOP_K_CHUNKS = int((os.getenv("TOP_K_CHUNKS") or "5").strip())

EMBEDDING_API_KEY = (os.getenv("EMBEDDING_API_KEY") or AZURE_OPENAI_API_KEY).strip()
EMBEDDING_BASE_URL = (os.getenv("EMBEDDING_BASE_URL") or AZURE_OPENAI_BASE_URL or "").strip() or None
EMBEDDING_MODEL = (os.getenv("EMBEDDING_MODEL") or "text-embedding-3-large").strip()
EMBEDDING_BATCH_SIZE = 96
EMBEDDING_DIM = int((os.getenv("EMBEDDING_DIM") or "3072").strip())  # dimensi asli text-embedding-3-large

SCOPE_SIM_HIGH = float(os.getenv("SCOPE_SIM_HIGH", "0.60"))
SCOPE_SIM_LOW = float(os.getenv("SCOPE_SIM_LOW", "0.30"))

WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID", "")
WOLFRAM_API_URL = "https://api.wolframalpha.com/v2/query"

SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "https://api.tavily.com/search")