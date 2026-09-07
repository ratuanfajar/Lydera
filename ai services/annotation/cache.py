import hashlib
import os
from pathlib import Path

import config


def get(namespace: str, *parts: str) -> str | None:
    path = _path(namespace, _key(parts))
    return path.read_text(encoding="utf-8") if path.exists() else None


def put(namespace: str, value: str, *parts: str) -> None:
    path = _path(namespace, _key(parts))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{id(value)}.tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)


def _key(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def _path(namespace: str, key: str) -> Path:
    return config.CACHE_DIR / namespace / f"{key}.txt"
