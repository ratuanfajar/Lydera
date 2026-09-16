from concurrent.futures import ThreadPoolExecutor

import config


def parallel_map(fn, items: list) -> list:
    """Sama seperti `[fn(item) for item in items]`, cuma dieksekusi paralel sebesar LLM_MAX_WORKERS.
    Urutan hasil tetap sama seperti sekuensial (pool.map, bukan as_completed)."""
    workers = max(1, min(config.LLM_MAX_WORKERS, len(items)))
    if workers == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
