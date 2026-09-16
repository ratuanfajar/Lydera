from pathlib import Path

from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

env_file = ".env.test" if os.getenv("APP_ENV") == "test" else ".env"
load_dotenv(env_file)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_AI_OUTPUT_DIR = PROJECT_ROOT / "ai-services" / "annotation" / "output"

class Settings(BaseSettings):
    BASE_URL: str = "http://localhost:8003"
    
    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_NAME: str = "Lydera"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Backend untuk Lydera"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = os.getenv("APP_SECRET_KEY")
    APP_DEBUG: bool = True

    # Server
    HOST: str = os.getenv("HOST","0.0.0.0")
    PORT: int = os.getenv("PORT","8000")

    # Database
    DB_ENGINE: str = os.getenv("DB_ENGINE","postgresql")
    DB_HOST: str = os.getenv("DB_HOST","localhost")
    DB_PORT: int = os.getenv("DB_PORT",5432)
    DB_NAME: str = os.getenv("DB_NAME")
    DB_USER: str = os.getenv("DB_USER")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB_URL: str = os.getenv("DB_URL")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL")

    # JWT
    ACCESS_TOKEN_EXPIRE_DAY: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAY", 1))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")

    # Prometheus
    PROMETHEUS_ENABLED: bool = False

    # --- AI SERVICES INTEGRATION ---
    # Will use the .env variable if provided, otherwise defaults to the physical folder
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", str(DEFAULT_AI_OUTPUT_DIR))

    # --- Chatbot ---
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", 3072))  # dimensi asli text-embedding-3-large
    CHAT_HISTORY_TURNS: int = int(os.getenv("CHAT_HISTORY_TURNS", 10))
    CHAT_HISTORY_TTL_SECONDS: int = int(os.getenv("CHAT_HISTORY_TTL_SECONDS", 1800))       # 30 menit
    QUERY_EMBEDDING_CACHE_TTL_SECONDS: int = int(os.getenv("QUERY_EMBEDDING_CACHE_TTL_SECONDS", 604800))  # 7 hari
    RETRIEVAL_CACHE_TTL_SECONDS: int = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", 3600))  # 1 jam

    @property
    def DATABASE_URL(self) -> str:
        if os.getenv("APP_ENV") == "testing":
            return os.getenv("DB_URL")
        return self.DB_URL
settings = Settings()