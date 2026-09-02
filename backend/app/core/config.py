from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

env_file = ".env.test" if os.getenv("APP_ENV") == "test" else ".env"
load_dotenv(env_file)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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

    # JWT
    ACCESS_TOKEN_EXPIRE_DAY: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAY", 1))
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")

    # Prometheus
    PROMETHEUS_ENABLED: bool = False

    @property
    def DATABASE_URL(self) -> str:
        if os.getenv("TESTING") == "True" or os.getenv("APP_ENV") == "testing":
            return os.getenv("DATABASE_URL")
        return self.DB_URL
settings = Settings()