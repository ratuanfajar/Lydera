from concurrent.futures import ThreadPoolExecutor

from annotation import config


def parallel_map(fn, items: list) -> list:
    workers = max(1, min(config.LLM_MAX_WORKERS, len(items)))
    if workers == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))
