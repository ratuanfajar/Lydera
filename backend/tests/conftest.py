import os

os.environ.setdefault("DB_URL", "postgresql+asyncpg://dummy:dummy@localhost:5432/dummy")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
