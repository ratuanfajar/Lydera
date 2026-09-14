from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    """Client Redis bersama (pool), dipakai chatbot untuk cache embedding/retrieval dan histori
    percakapan hot. Modul lain (`mineru_tasks.py`, `progress_tasks.py`, `router.py` di domain
    contents) masih bikin koneksi ad-hoc sendiri -- tidak diubah di sini supaya tidak menyentuh
    kode yang sudah stabil, tapi kode baru sebaiknya reuse client ini."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
