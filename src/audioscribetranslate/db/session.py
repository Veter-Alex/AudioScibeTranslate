from collections.abc import AsyncGenerator
from typing import AsyncGenerator

"""
Модуль для создания асинхронной сессии SQLAlchemy и получения подключения к базе данных.

Example:
    async with get_db() as session:
        result = await session.execute(...)
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from audioscribetranslate.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
# Async SQLAlchemy engine для подключения к базе данных

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
# Фабрика асинхронных сессий


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный генератор для получения сессии базы данных.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy.

    Example:
        async with get_db() as session:
            result = await session.execute(...)

    Warning:
        Сессия автоматически закрывается после завершения работы.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
