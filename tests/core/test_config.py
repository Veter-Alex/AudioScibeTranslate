from typing import Iterator

"""
:module: src/audioscribetranslate/core/config.py
Тесты конфигурации приложения и генерации URL для БД/Redis.
Требования: CONFIG-101, CONFIG-102, CONFIG-103
"""
import os

import pytest

from src.audioscribetranslate.core.config import Settings, create_settings, get_env_file


# SETUP: Сохраняем оригинальное окружение
@pytest.fixture(autouse=True)
def restore_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    orig_env = os.environ.get("ENV")
    yield
    if orig_env is not None:
        monkeypatch.setenv("ENV", orig_env)
    else:
        monkeypatch.delenv("ENV", raising=False)


def test_get_env_file_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: ENV=local возвращает .env.local (CONFIG-101)"""
    monkeypatch.setenv("ENV", "local")
    assert get_env_file() == ".env.local"

def test_get_env_file_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge case: ENV=production возвращает .env.production (CONFIG-101)"""
    monkeypatch.setenv("ENV", "production")
    assert get_env_file() == ".env.production"

def test_get_env_file_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Негативный тест: ENV=unknown возвращает .env.local (CONFIG-101, баг #21)"""
    monkeypatch.setenv("ENV", "unknown")
    assert get_env_file() == ".env.local"

def test_settings_whisper_models_list() -> None:
    """Happy path: whisper_models_list парсит строку в список (CONFIG-102)"""
    s = Settings(whisper_models="base,small,medium")
    assert s.whisper_models_list == ["base", "small", "medium"]

def test_settings_whisper_models_list_empty() -> None:
    """Edge case: пустая строка whisper_models (CONFIG-102)"""
    s = Settings(whisper_models="")
    assert s.whisper_models_list == []

def test_settings_database_url() -> None:
    """Happy path: database_url формируется корректно (CONFIG-103)"""
    s = Settings(postgres_user="u", postgres_password="p", postgres_host="h", postgres_port=123, postgres_db="d")
    url = s.database_url
    assert url == "postgresql+asyncpg://u:p@h:123/d"

def test_settings_sync_database_url() -> None:
    """Happy path: sync_database_url формируется корректно (CONFIG-103)"""
    s = Settings(postgres_user="u", postgres_password="p", postgres_host="h", postgres_port=123, postgres_db="d")
    url = s.sync_database_url
    assert url == "postgresql+psycopg2://u:p@h:123/d"

def test_create_settings_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge case: create_settings использует правильный env_file (CONFIG-101)"""
    monkeypatch.setenv("ENV", "docker")
    s = create_settings()
    assert s.model_config["env_file"] == ".env"
    assert s.model_config["env_file"] == ".env"
