import os
from functools import lru_cache
from typing import Any, List

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


def get_env_file() -> str:
    """Динамически определяет файл окружения на основе ENV переменной."""
    env_mapping = {
        "local": ".env.local",
        "docker": ".env",
        "production": ".env.production",
    }

    current_env = os.getenv("ENV", "local")
    return env_mapping.get(current_env, ".env.local")


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

    @property
    def current_env_file(self) -> str:
        """Возвращает текущий используемый файл окружения."""
        return get_env_file()

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

    model_config = {"env_file_encoding": "utf-8", "extra": "ignore"}


def create_settings(**kwargs: Any) -> Settings:
    """Создает экземпляр Settings с правильным env_file."""
    env_file = get_env_file()

    # Создаем динамический класс с правильным env_file
    class DynamicSettings(Settings):
        model_config = Settings.model_config.copy()

    DynamicSettings.model_config["env_file"] = env_file

    return DynamicSettings(**kwargs)


@lru_cache
def get_settings() -> Settings:
    return create_settings()
