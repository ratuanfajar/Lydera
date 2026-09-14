"""Ekstensi client LLM untuk chatbot: embeddings + chat completion dengan tool calling.

Reuse `annotation/llm.py` (client OpenRouter + retry) untuk completion biasa, tapi embeddings
dipisah ke client sendiri karena base_url/model beda (lihat config.EMBEDDING_*)."""

import time
from functools import lru_cache

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

import config
import llm as annotation_llm

RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
MAX_RETRIES = 5
BACKOFF_BASE = 2


@lru_cache(maxsize=1)
def _embedding_client() -> OpenAI:
    return OpenAI(base_url=config.EMBEDDING_BASE_URL, api_key=config.EMBEDDING_API_KEY)


def _retry(fn, **kwargs):
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
    """Embed sekumpulan teks sekaligus (batch), balikkan satu vector per teks, urutan terjaga."""
    if not texts:
        return []
    response = _retry(
        _embedding_client().embeddings.create,
        model=model or config.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_text(text: str, model: str | None = None) -> list[float]:
    return embed_texts([text], model=model)[0]


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
    tool_choice: str | dict = "auto",
):
    """Satu giliran chat completion dengan tool calling. Balikkan message object OpenAI mentah
    (punya `.content` dan `.tool_calls`) supaya pemanggil bisa loop sampai model berhenti minta tool."""
    response = _retry(
        annotation_llm.client().chat.completions.create,
        model=model or config.CHAT_MODEL,
        max_tokens=max_tokens or config.CHAT_MAX_TOKENS,
        extra_body={"reasoning": {"enabled": False}},
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
    )
    return response.choices[0].message
