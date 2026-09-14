from redis.asyncio import Redis
from app.core.config import settings

_redis_client: Redis | None = None

def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30, # Pings Redis every 30s to prune stale connections
            retry_on_timeout=True,     # Automatically reconnects on dropped timeouts
            socket_connect_timeout=5, # Prevents hanging connections on startup
        )
    return _redis_client

async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None