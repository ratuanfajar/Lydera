import os
from pathlib import Path

from dotenv import load_dotenv

ANNOTATION_DIR = Path(__file__).parent
AI_SERVICE_DIR = ANNOTATION_DIR.parent

load_dotenv(AI_SERVICE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL") or "").strip() or None

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

# --- Chatbot (RAG) ---
CHAT_MODEL = (os.getenv("CHAT_MODEL") or MODEL).strip()
CHAT_MAX_TOKENS = int((os.getenv("CHAT_MAX_TOKENS") or "1024").strip())
MAX_TOOL_ITERATIONS = int((os.getenv("MAX_TOOL_ITERATIONS") or "10").strip())
TOP_K_CHUNKS = int((os.getenv("TOP_K_CHUNKS") or "5").strip())

# Embedding lewat OpenRouter (endpoint /embeddings, OpenAI-compatible, reuse OPENROUTER_API_KEY) --
# model butuh prefix provider (mis. "openai/text-embedding-3-small"). Bisa diarahkan ke provider
# lain lewat env ini kalau perlu.
EMBEDDING_API_KEY = (os.getenv("EMBEDDING_API_KEY") or OPENROUTER_API_KEY).strip()
EMBEDDING_BASE_URL = (os.getenv("EMBEDDING_BASE_URL") or OPENROUTER_BASE_URL or "").strip() or None
EMBEDDING_MODEL = (os.getenv("EMBEDDING_MODEL") or "openai/text-embedding-3-large").strip()
EMBEDDING_DIM = int((os.getenv("EMBEDDING_DIM") or "3072").strip())  # dimensi asli text-embedding-3-large

# Scope gate -- similarity cosine antara pertanyaan siswa dan topic anchor (mapel/CP domain/bab).
SCOPE_SIM_HIGH = float(os.getenv("SCOPE_SIM_HIGH", "0.32"))
SCOPE_SIM_LOW = float(os.getenv("SCOPE_SIM_LOW", "0.12"))

# Wolfram Alpha Full Results API -- masih tier gratis (2000 call/bulan, NON-KOMERSIAL saja, lihat
# https://products.wolframalpha.com/api/pricing). Step-by-step solution TIDAK termasuk tier ini --
# dipakai untuk cross-check hasil singkat lewat pod "Result" (lihat external_tools._extract_answer).
WOLFRAM_APP_ID = os.getenv("WOLFRAM_APP_ID", "")
WOLFRAM_API_URL = "https://api.wolframalpha.com/v2/query"

# Web search akademik (domain-filtered) -- lihat chatbot/trusted_domains.py.
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "https://api.tavily.com/search")
