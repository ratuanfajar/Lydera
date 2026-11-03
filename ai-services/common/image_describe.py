from pathlib import Path
from typing import Callable

from common import cache, llm


def describe_cached(system: str, user: str, key: tuple, image: Callable[[], Path]) -> str:
    """Deskripsi gambar lewat model vision dengan cache; `image` baru dipanggil saat cache kosong."""
    cached = cache.get("image", *key)
    if cached is None:
        cached = llm.complete_vision(system, user, image())
        cache.put("image", cached, *key)
    return cached
