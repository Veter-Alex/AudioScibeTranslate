import os
from functools import lru_cache
from typing import Any, List, Optional

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


def get_env_file() -> str:
    """
    Динамически определяет файл окружения на основе переменной окружения ENV.

    Returns:
        str: Имя файла окружения (например, .env.local, .env, .env.production).

    Example:
        >>> os.environ["ENV"] = "production"
        >>> get_env_file()
        '.env.production'

    Note:
        Если переменная ENV не установлена, используется .env.local.
    """
    env_mapping = {
        "local": ".env.local",
        "docker": ".env",
        "production": ".env.production",
    }

    current_env = os.getenv("ENV", "local")
    return env_mapping.get(current_env, ".env.local")


def is_running_in_docker() -> bool:
    """
    Определяет, выполняется ли код внутри Docker контейнера.

    Returns:
        bool: True если код выполняется в Docker, False иначе.
    """
    # Проверяем наличие файла /.dockerenv (стандартный индикатор Docker)
    if os.path.exists("/.dockerenv"):
        return True
    
    # Проверяем переменные окружения, устанавливаемые Docker
    if os.getenv("DOCKER_CONTAINER"):
        return True
        
    # Проверяем контрольную группу процесса (в Docker содержит "docker")
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except (FileNotFoundError, PermissionError):
        pass
    
    return False


class Settings(BaseSettings):
    def __init__(self, **kwargs: Any) -> None:
        # Сначала определяем env_file
        env_file = kwargs.pop('_env_file', None)
        if env_file is None:
            env_file = get_env_file()
        
        # Создаем объект с правильным env_file
        super().__init__(_env_file=env_file, **kwargs)
        self._used_env_file = env_file
        
        # Устанавливаем хост базы данных в зависимости от того, запускается ли код в Docker
        if not self.postgres_host:
            if is_running_in_docker():
                self.postgres_host = "db"  # Внутри Docker используем сервис 'db'
            else:
                self.postgres_host = "localhost"  # Снаружи Docker используем localhost
    """
    Класс конфигурации приложения, основанный на pydantic BaseSettings.

    Все параметры могут быть переопределены через переменные окружения или .env-файл.

    Attributes:
        postgres_host (str): Хост PostgreSQL.
        postgres_port (int): Порт PostgreSQL.
        postgres_db (str): Имя базы данных.
        postgres_user (str): Имя пользователя.
        postgres_password (str): Пароль пользователя.
        redis_url (str): URL Redis.
        secret_key (str): Секретный ключ приложения.
        celery_broker_url (str): URL брокера Celery.
        celery_result_backend (str): URL backend'а Celery.
        whisper_models (str): Список моделей Whisper через запятую.
        memory_threshold_gb (int): Порог памяти для масштабирования воркеров.
        max_workers (int): Максимальное количество воркеров.
        min_workers (int): Минимальное количество воркеров.
        memory_check_interval (int): Интервал проверки памяти (сек).
        worker_memory_limit_gb (int): Лимит памяти на воркер.
        enable_auto_scaling (bool): Включить автомасштабирование воркеров.

    Example:
        settings = Settings()
        print(settings.postgres_host)
    """
    postgres_host: str = ""  # Будет установлен в __init__
    postgres_port: int = 5432
    postgres_db: str = "audioscribetranslate"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "your-secret-key"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    # Whisper модели
    whisper_models: str = "base,small,medium,large"

    # Настройки динамического масштабирования воркеров
    memory_threshold_gb: int = 8
    max_workers: int = 6
    min_workers: int = 1
    memory_check_interval: int = 30
    worker_memory_limit_gb: int = 4
    enable_auto_scaling: bool = True

    @property
    def whisper_models_list(self) -> list[str]:
        """
        Возвращает список моделей Whisper, указанных в конфиге.

        Returns:
            list[str]: Список моделей Whisper.

        Example:
            >>> settings.whisper_models = "base,small,medium"
            >>> settings.whisper_models_list
            ['base', 'small', 'medium']
        """
        if isinstance(self.whisper_models, str):
            return [m.strip() for m in self.whisper_models.split(",") if m.strip()]
        return []

    @property
    def current_env_file(self) -> str:
        """
        Возвращает фактически используемый файл окружения.

        Returns:
            str: Имя файла окружения.
        """
        # Если явно передан _env_file, возвращаем его
        if hasattr(self, '_used_env_file'):
            return str(self._used_env_file)
        env_file = getattr(self, '_env_file', None)
        if env_file:
            return str(env_file)
        return get_env_file()

    @property
    def database_url(self) -> str:
        """
        Формирует асинхронный URL для подключения к базе данных PostgreSQL.

        Returns:
            str: Строка подключения для asyncpg.
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        Формирует синхронный URL для подключения к базе данных PostgreSQL.

        Returns:
            str: Строка подключения для psycopg2.
        """
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file_encoding": "utf-8", "extra": "ignore"}


def create_settings(**kwargs: Any) -> Settings:
    """
    Создает экземпляр Settings с правильным env_file.

    Args:
        **kwargs: Параметры для инициализации Settings.

    Returns:
        Settings: Экземпляр конфигурации.

    Example:
        >>> settings = create_settings(postgres_host='db')
        >>> print(settings.postgres_host)
        'db'
    """
    env_file = get_env_file()

    # Создаем динамический класс с правильным env_file
    class DynamicSettings(Settings):
        model_config = Settings.model_config.copy()

    DynamicSettings.model_config["env_file"] = env_file

    return DynamicSettings(**kwargs)


def get_settings() -> Settings:
    """
    Всегда возвращает экземпляр Settings с актуальным env-файлом (без кэширования по ENV).

    Returns:
        Settings: Глобальный экземпляр конфигурации.

    Example:
        >>> settings = get_settings()
        >>> print(settings.redis_url)
    """
    return create_settings()
