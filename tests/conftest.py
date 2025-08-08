"""Per-test isolated async database session to avoid event loop & concurrency issues."""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.db.session import get_db
from audioscribetranslate.main import app

# Ensure selector loop on Windows (asyncpg requirement for reliability)
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():  # type: ignore
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    # Apply migrations to head (once per engine creation) using Alembic programmatic API
    # We assume alembic.ini is at project root.
    alembic_cfg = Config(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    )
    # Override SQLAlchemy URL to the test database URL (async -> sync needed for alembic so strip +asyncpg)
    sync_url = settings.sync_database_url
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")
    # Pre-clean to guarantee empty state for this test's engine
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
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    maker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture(autouse=True)
def override_get_db(db_session: AsyncSession):
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    return
