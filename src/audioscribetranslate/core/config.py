import os
from functools import lru_cache
from typing import List

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "your-secret-key"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    whisper_models: str = ""

    @property
    def whisper_models_list(self) -> list[str]:
        if isinstance(self.whisper_models, str):
            return [m.strip() for m in self.whisper_models.split(",") if m.strip()]
        return []

    class Config:
        env_file = ".env.local" if os.getenv("ENV", "local") == "local" else ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
