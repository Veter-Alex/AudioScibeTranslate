from typing import Iterator

from sqlalchemy import delete, func, insert, select

"""
:module: src/audioscribetranslate/db/utils.py
Тесты создания администратора в базе данных.
Требования: DB-101, DB-102
# Проверка сценария из JIRA DB-228
"""
import asyncio

import pytest

from src.audioscribetranslate.db.utils import create_admin_if_not_exists
from src.audioscribetranslate.models.user import User


@pytest.mark.asyncio
async def test_create_admin_if_not_exists_creates_new_admin(db_session):
    """Happy path: создаёт нового администратора, если его нет (DB-101)"""
    # SETUP: Очищаем таблицу пользователей
    await db_session.execute(delete(User))
    await db_session.commit()
    # EXECUTION: Создаём админа
    await create_admin_if_not_exists("admin", "hashed_pass", db_session)
    # VERIFICATION: Проверяем наличие
    result = await db_session.execute(select(User).where(User.name == "admin"))
    admin = result.scalar_one_or_none()
    assert admin is not None

@pytest.mark.asyncio
async def test_create_admin_if_not_exists_existing_admin(db_session):
    """Edge case: админ уже существует — не создаёт дубликат (DB-102)"""
    # SETUP: Создаём админа вручную
    await db_session.execute(delete(User))
    await db_session.execute(insert(User).values(name="admin", hashed_password="hashed_pass", is_active=1, is_admin=1))
    await db_session.commit()
    await create_admin_if_not_exists("admin", "hashed_pass", db_session)
    result = await db_session.execute(select(func.count()).select_from(User).where(User.name == "admin"))
    count = result.scalar()
    assert count == 1

@pytest.mark.asyncio
async def test_create_admin_if_not_exists_invalid_name(db_session):
    """Негативный тест: пустое имя администратора (DB-102, баг #44)"""
    # EXECUTION: Пытаемся создать админа с пустым именем
    await create_admin_if_not_exists("", "hashed_pass", db_session)
    result = await db_session.execute(select(func.count()).select_from(User).where(User.name == ""))
    count = result.scalar()
    assert count == 0
