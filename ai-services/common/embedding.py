import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

from common import config

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
MAX_RETRIES = 5
BACKOFF_BASE = 2


@lru_cache(maxsize=1)
def _embedding_client() -> OpenAI:
    return OpenAI(base_url=config.EMBEDDING_BASE_URL, api_key=config.EMBEDDING_API_KEY)


def retry(fn, **kwargs):
    delay = BACKOFF_BASE
    for attempt in range(MAX_RETRIES):
        try:
            return fn(**kwargs)
        except RETRYABLE:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed sekumpulan teks: dipecah per EMBEDDING_BATCH_SIZE dan dikirim paralel; satu vector per teks, urutan terjaga."""
    if not texts:
        return []
    batches = [texts[start:start + config.EMBEDDING_BATCH_SIZE] for start in range(0, len(texts), config.EMBEDDING_BATCH_SIZE)]

    def embed_batch(batch: list[str]) -> list[list[float]]:
        response = retry(_embedding_client().embeddings.create, model=model or config.EMBEDDING_MODEL, input=batch)
        return [item.embedding for item in response.data]

    with ThreadPoolExecutor(max_workers=min(config.EMBEDDING_MAX_WORKERS, len(batches))) as pool:
        return [vector for batch in pool.map(embed_batch, batches) for vector in batch]


def embed_text(text: str, model: str | None = None) -> list[float]:
    return embed_texts([text], model=model)[0]
