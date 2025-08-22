"""
Простые unit тесты для системы конфигурации окружений
Не зависят от базы данных и других внешних сервисов
"""

import os
from unittest.mock import patch

import pytest

from audioscribetranslate.core.config import Settings, get_settings


def test_local_environment_config():
    """Тест загрузки конфигурации для локального окружения"""
    with patch.dict(os.environ, {"ENV": "local"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

        # Проверяем, что используется правильный env файл
        assert settings.Config.env_file == ".env.local"


def test_docker_environment_config():
    """Тест загрузки конфигурации для Docker окружения"""
    with patch.dict(os.environ, {"ENV": "docker"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

        # Проверяем, что используется правильный env файл
        assert settings.Config.env_file == ".env"


def test_production_environment_config():
    """Тест загрузки конфигурации для продакшн окружения"""
    with patch.dict(os.environ, {"ENV": "production"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

        # Проверяем, что используется правильный env файл
        assert settings.Config.env_file == ".env.production"


def test_default_environment_is_local():
    """Тест, что по умолчанию используется локальное окружение"""
    with patch.dict(os.environ, {}, clear=True):
        # Удаляем ENV переменную если она есть
        os.environ.pop("ENV", None)

        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

        # По умолчанию должен использоваться .env.local
        assert settings.Config.env_file == ".env.local"


def test_unknown_environment_falls_back_to_local():
    """Тест, что неизвестное окружение использует локальную конфигурацию"""
    with patch.dict(os.environ, {"ENV": "unknown"}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()

        # Неизвестное окружение должно использовать .env.local
        assert settings.Config.env_file == ".env.local"


def test_whisper_models_list_parsing():
    """Тест парсинга списка Whisper моделей"""
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


def test_database_url_generation():
    """Тест генерации URL для базы данных"""
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
def test_env_file_selection(env_value, expected_file):
    """Параметризованный тест выбора env файла"""
    with patch.dict(os.environ, {"ENV": env_value}):
        # Очищаем кеш перед тестом
        get_settings.cache_clear()

        settings = Settings()
        assert settings.Config.env_file == expected_file


def test_environment_file_existence():
    """Тест проверки существования основных env файлов"""
    from pathlib import Path

    # Проверяем наличие основных env файлов
    expected_files = [".env.local", ".env", ".env.example"]

    for env_file in expected_files:
        file_path = Path(env_file)
        if file_path.exists():
            # Проверяем, что файл не пустой
            assert file_path.stat().st_size > 0, f"{env_file} не должен быть пустым"


# Очистка после всех тестов
def teardown_module():
    """Очистка после модуля тестов"""
    get_settings.cache_clear()
