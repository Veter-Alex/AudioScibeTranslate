"""
:module: src/audioscribetranslate/models/user.py
Тесты модели пользователя.
Требования: USER-101, USER-102
"""
import pytest

from src.audioscribetranslate.models.user import User


def test_user_model_fields() -> None:
    """Happy path: поля модели User соответствуют требованиям (USER-101)"""
    user = User(name="alice", hashed_password="hash", is_active=1, is_admin=1)
    assert user.name == "alice"
    assert user.hashed_password == "hash"
    assert user.is_active == 1
    assert user.is_admin == 1

def test_user_model_default_values() -> None:
    """Edge case: значения по умолчанию для is_active и is_admin (USER-102)"""
    user = User(name="bob", hashed_password="hash")
    assert user.is_active == 1
    assert user.is_admin == 0

def test_user_model_unique_name() -> None:
    """Негативный тест: имя пользователя должно быть уникальным (USER-102, баг #66)"""
    # MOCK: Проверяем, что поле name уникальное
    assert User.__table__.columns.name.unique
    # MOCK: Проверяем, что поле name уникальное
    assert User.__table__.columns.name.unique
