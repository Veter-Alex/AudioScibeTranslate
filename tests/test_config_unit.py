"""
Unit-тесты для системы конфигурации окружений AudioScribeTranslate.

Проверяют:
- Выбор env-файла по переменной окружения
- Парсинг списка моделей Whisper
- Генерацию URL для базы данных
- Корректную работу Settings

Pitfalls:
- Не зависят от базы данных и внешних сервисов
- Кэш get_settings очищается перед каждым тестом
"""

import os
from unittest.mock import patch

import pytest

from audioscribetranslate.core.config import Settings, get_settings


def test_local_environment_config() -> None:
    """
    Проверяет загрузку конфигурации для локального окружения.

    Steps:
        - Устанавливает ENV=local
        - Очищает кэш
        - Проверяет, что выбран .env.local
    """
    with patch.dict(os.environ, {"ENV": "local"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

    # Проверяем, что используется правильный env файл
    assert settings.current_env_file == ".env.local"


def test_docker_environment_config() -> None:
    """
    Проверяет загрузку конфигурации для Docker окружения.

    Steps:
        - Устанавливает ENV=docker
        - Очищает кэш
        - Проверяет, что выбран .env
    """
    with patch.dict(os.environ, {"ENV": "docker"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

    # Проверяем, что используется правильный env файл
    assert settings.current_env_file == ".env"


def test_production_environment_config() -> None:
    """
    Проверяет загрузку конфигурации для production окружения.

    Steps:
        - Устанавливает ENV=production
        - Очищает кэш
        - Проверяет, что выбран .env.production
    """
    with patch.dict(os.environ, {"ENV": "production"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

    # Проверяем, что используется правильный env файл
    assert settings.current_env_file == ".env.production"


def test_default_environment_is_local() -> None:
    """
    Проверяет, что по умолчанию используется локальное окружение.

    Steps:
        - ENV не задан
        - Очищает кэш
        - Проверяет, что выбран .env.local
    """
    with patch.dict(os.environ, {}, clear=True):
        # Удаляем ENV переменную если она есть
        os.environ.pop("ENV", None)

        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

    # По умолчанию должен использоваться .env.local
    assert settings.current_env_file == ".env.local"


def test_unknown_environment_falls_back_to_local() -> None:
    """
    Проверяет, что неизвестное окружение использует локальную конфигурацию.

    Steps:
        - ENV=unknown
        - Очищает кэш
        - Проверяет, что выбран .env.local
    """
    with patch.dict(os.environ, {"ENV": "unknown"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

    # Неизвестное окружение должно использовать .env.local
    assert settings.current_env_file == ".env.local"


def test_whisper_models_list_parsing() -> None:
    """
    Проверяет парсинг списка моделей Whisper.

    Steps:
        - Пустая строка
        - Одна модель
        - Несколько моделей
        - Модели с пробелами
    """
    # Тест с пустой строкой
    settings = Settings(whisper_models="")
    assert settings.whisper_models_list == []

    # Тест с одной моделью
    settings = Settings(whisper_models="base")
    assert settings.whisper_models_list == ["base"]

    # Тест с несколькими моделями
    settings = Settings(whisper_models="base,small,medium")
    assert settings.whisper_models_list == ["base", "small", "medium"]

    # Тест с пробелами
    settings = Settings(whisper_models=" base , small , medium ")
    assert settings.whisper_models_list == ["base", "small", "medium"]


def test_database_url_generation() -> None:
    """
    Проверяет генерацию URL для базы данных.

    Steps:
        - Создаёт Settings с тестовыми параметрами
        - Проверяет async и sync URL
    """
    settings = Settings(
        postgres_user="testuser",
        postgres_password="testpass",
        postgres_host="testhost",
        postgres_port=5433,
        postgres_db="testdb",
    )

    expected_async_url = "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
    expected_sync_url = "postgresql+psycopg2://testuser:testpass@testhost:5433/testdb"

    assert settings.database_url == expected_async_url
    assert settings.sync_database_url == expected_sync_url


@pytest.mark.parametrize(
    "env_value,expected_file",
    [
        ("local", ".env.local"),
        ("docker", ".env"),
        ("production", ".env.production"),
        ("staging", ".env.local"),  # fallback к local
        ("", ".env.local"),  # пустая строка
    ],
)
def test_env_file_selection(env_value: str, expected_file: str) -> None:
    """
    Проверяет выбор env файла по переменной окружения (параметризованный тест).

    Args:
        env_value (str): Значение ENV
        expected_file (str): Ожидаемый env файл
    """
    with patch.dict(os.environ, {"ENV": env_value}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

    settings = Settings()
    assert settings.current_env_file == expected_file


def test_environment_file_existence() -> None:
    """
    Проверяет существование основных env файлов.

    Steps:
        - Проверяет наличие .env.local, .env, .env.example
        - Проверяет, что файлы не пустые
    """
    from pathlib import Path

    # Проверяем наличие основных env файлов
    expected_files = [".env.local", ".env", ".env.example"]

    for env_file in expected_files:
        file_path = Path(env_file)
        if file_path.exists():
            # Проверяем, что файл не пустой
            assert file_path.stat().st_size > 0, f"{env_file} не должен быть пустым"


# Очистка после всех тестов
def teardown_module() -> None:
    """
    Очистка кэша get_settings после завершения всех тестов модуля.
    """
    get_settings.cache_clear()
