"""
:module: src/audioscribetranslate/core/files.py
Проверка создания и получения структуры uploaded_files для аудиофайлов.
Требования: FILES-101, FILES-102
"""

import os
import shutil
from typing import Iterator

import pytest

from src.audioscribetranslate.core.files import (
    create_uploaded_files_structure,
    get_uploaded_files_dir,
)

# SETUP: Тестовые данные для моделей и пользователей
MODELS = ["base", "small"]
USERS = ["alice", "bob"]

@pytest.fixture(autouse=True)
def cleanup_uploaded_files() -> Iterator[None]:
    # CLEANUP: Удаляем тестовую структуру перед и после теста
    dir_path = get_uploaded_files_dir()
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    yield
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)


def test_get_uploaded_files_dir_returns_absolute_path() -> None:
    """Базовый сценарий: get_uploaded_files_dir возвращает абсолютный путь (FILES-101)"""
    # EXECUTION: Получаем путь
    path = get_uploaded_files_dir()
    # VERIFICATION: Проверяем абсолютность
    assert os.path.isabs(path)
    assert path.endswith("uploaded_files")


def test_create_uploaded_files_structure_creates_dirs() -> None:
    """Happy path: создание структуры uploaded_files/{model}/{user} (FILES-102)"""
    # EXECUTION: Создаём структуру
    create_uploaded_files_structure(MODELS, USERS)
    base_dir = get_uploaded_files_dir()
    # VERIFICATION: Проверяем наличие директорий
    for model in MODELS:
        for user in USERS:
            user_dir = os.path.join(base_dir, model, user)
            assert os.path.isdir(user_dir)


def test_create_uploaded_files_structure_with_empty_lists() -> None:
    """Edge case: пустые списки моделей и пользователей (FILES-102, баг #12)"""
    # EXECUTION: Пустые списки
    create_uploaded_files_structure([], [])
    base_dir = get_uploaded_files_dir()
    # VERIFICATION: Только базовая папка создана
    assert os.path.isdir(base_dir)
    # Проверяем, что нет вложенных директорий
    assert not any(os.scandir(base_dir))


def test_create_uploaded_files_structure_invalid_base_dir() -> None:
    """Негативный тест: несуществующий путь base_dir (FILES-102)"""
    # EXECUTION: Передаём невалидный путь
    invalid_dir = os.path.join(get_uploaded_files_dir(), "..", "invalid_path")
    create_uploaded_files_structure(["base"], ["alice"], base_dir=invalid_dir)
    # VERIFICATION: Директория должна быть создана
    assert os.path.isdir(os.path.join(invalid_dir, "base", "alice"))

# MOCK: Проверка повторного вызова (структура не должна ломаться)
def test_create_uploaded_files_structure_idempotent() -> None:
    """Edge case: повторный вызов не приводит к ошибке (FILES-102)"""
    create_uploaded_files_structure(MODELS, USERS)
    create_uploaded_files_structure(MODELS, USERS)
    base_dir = get_uploaded_files_dir()
    for model in MODELS:
        for user in USERS:
            user_dir = os.path.join(base_dir, model, user)
            assert os.path.isdir(user_dir)
    base_dir = get_uploaded_files_dir()
    for model in MODELS:
        for user in USERS:
            user_dir = os.path.join(base_dir, model, user)
            assert os.path.isdir(user_dir)
