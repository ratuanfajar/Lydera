import os

from common import config as common_config

CHAT_MODEL = (os.getenv("CHAT_MODEL") or "gpt-5.4-mini").strip()
CHAT_MAX_TOKENS = int((os.getenv("CHAT_MAX_TOKENS") or "1024").strip())
MAX_TOOL_ITERATIONS = int((os.getenv("MAX_TOOL_ITERATIONS") or "10").strip())
TOP_K_CHUNKS = int((os.getenv("TOP_K_CHUNKS") or "5").strip())

EMBEDDING_API_KEY = common_config.EMBEDDING_API_KEY
EMBEDDING_BASE_URL = common_config.EMBEDDING_BASE_URL
EMBEDDING_MODEL = common_config.EMBEDDING_MODEL
EMBEDDING_BATCH_SIZE = common_config.EMBEDDING_BATCH_SIZE
EMBEDDING_DIM = common_config.EMBEDDING_DIM

SCOPE_SIM_HIGH = float((os.getenv("SCOPE_SIM_HIGH") or "").strip() or "0.60")
SCOPE_SIM_LOW = float((os.getenv("SCOPE_SIM_LOW") or "").strip() or "0.30")

SEARCH_API_KEY = os.getenv("SEARCH_API_KEY") or ""
SEARCH_API_URL = os.getenv("SEARCH_API_URL") or "https://api.tavily.com/search"
OER_MIN_SCORE = float((os.getenv("OER_MIN_SCORE") or "").strip() or "0.6")
