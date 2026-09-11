import taskiq_redis
from app.core.config import settings

result_backend = taskiq_redis.RedisAsyncResultBackend(
    redis_url=settings.REDIS_URL,
    result_ex_time=3600, 
)

broker = taskiq_redis.ListQueueBroker(
    url=settings.REDIS_URL,
    socket_timeout=None,    # Prevents worker crash/timeout during idle queue polling
    socket_keepalive=True,  # Maintains TCP health on Windows/Docker
).with_result_backend(result_backend)