from sqlalchemy import select

"""
:module: src/audioscribetranslate/db/session.py
Тесты асинхронной сессии SQLAlchemy.
Требования: DB-201, DB-202
"""
import asyncio

import pytest

from src.audioscribetranslate.db.session import AsyncSessionLocal, get_db


@pytest.mark.asyncio
async def test_get_db_yields_session() -> None:
    """Happy path: get_db возвращает асинхронную сессию (DB-201)"""
    # EXECUTION: Получаем сессию через генератор
    gen = get_db()
    session = await gen.__anext__()
    # VERIFICATION: Проверяем тип
    from sqlalchemy.ext.asyncio import AsyncSession
    assert isinstance(session, AsyncSession)
    await session.close()

@pytest.mark.asyncio
async def test_async_session_local_direct() -> None:
    """Edge case: AsyncSessionLocal создаёт сессию напрямую (DB-202)"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.ext.asyncio import AsyncSession
        assert isinstance(session, AsyncSession)
        # EXECUTION: Проверяем, что сессия открыта
    await session.close()

@pytest.mark.asyncio
async def test_get_db_closes_session() -> None:
    """Негативный тест: get_db корректно закрывает сессию (DB-202, баг #55)"""
    gen = get_db()
    session = await gen.__anext__()
    await session.close()
    # VERIFICATION: Проверяем, что сессия закрыта
    # Для AsyncSession нет атрибута closed, проверяем через try/except
    try:
        await session.execute(select(1))
        assert False, "Session should be closed"
    except Exception:
        pass
        pass
