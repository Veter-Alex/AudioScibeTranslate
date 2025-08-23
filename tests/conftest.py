import pytest
import pytest_asyncio
from sqlalchemy import text

"""
Фикстуры для изолированного асинхронного тестирования с отдельной базой данных.

Обеспечивают:
- Чистую базу для каждого теста
- Автоматическую миграцию Alembic
- Переопределение зависимостей FastAPI

Pitfalls:
- Alembic должен быть корректно настроен
- TRUNCATE очищает все таблицы, не используйте в production
"""

import sys
from pathlib import Path

SRC_PATH = Path(__file__).parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Generator

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.db.session import get_db
from audioscribetranslate.main import app

# Для Windows: гарантируем корректную работу event loop с asyncpg
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Создаёт отдельный event loop для асинхронных тестов.

    Returns:
        event_loop: Новый экземпляр event loop
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
    return None


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[object, None]:
    """
    Создаёт асинхронный движок SQLAlchemy для тестовой базы.
    Применяет миграции Alembic и очищает все таблицы.

    Yields:
        AsyncEngine: Асинхронный движок для тестов

    Pitfalls:
        - Alembic должен быть настроен на тестовую БД
        - TRUNCATE удаляет все данные
    """
    # Принудительно используем localhost для тестов
    from audioscribetranslate.core.config import Settings
    settings = Settings(postgres_host="localhost")
    engine = create_async_engine(settings.database_url, future=True)
    # Применяем миграции Alembic к тестовой БД
    alembic_cfg = Config(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    )
    sync_url = settings.sync_database_url
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")
    # Очищаем все таблицы
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE summaries, translations, transcripts, audio_files, users RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Создаёт асинхронную сессию БД для каждого теста.

    Yields:
        AsyncSession: Сессия для работы с тестовой БД
    """
    maker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture(autouse=True)
def override_get_db(db_session: AsyncSession) -> None:
    """
    Переопределяет зависимость get_db в FastAPI для использования тестовой сессии.

    Args:
        db_session (AsyncSession): Сессия тестовой БД
    """
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    return

    app.dependency_overrides[get_db] = _override
    return
