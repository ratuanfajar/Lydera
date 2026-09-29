from taskiq import TaskiqEvents, TaskiqState
import taskiq_redis
from app.core.config import settings
from app.core.redis import close_redis_client

result_backend = taskiq_redis.RedisAsyncResultBackend(
    redis_url=settings.REDIS_URL,
    result_ex_time=3600, 
)

broker = taskiq_redis.ListQueueBroker(
    url=settings.REDIS_URL,
    socket_timeout=None,    # Prevents worker crash/timeout during idle queue polling
    socket_keepalive=True,  # Maintains TCP health on Windows/Docker
).with_result_backend(result_backend)

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown_event(state: TaskiqState) -> None:
    await close_redis_client()