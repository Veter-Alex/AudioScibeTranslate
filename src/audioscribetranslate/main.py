"""
Главная точка входа FastAPI-приложения AudioScribeTranslate.

Инициализирует все роутеры, настраивает жизненный цикл приложения,
создаёт структуру папок для загруженных файлов и администратора.

Архитектурные принципы:
- Чистый startup/shutdown через lifespan
- Автоматическая инициализация моделей и пользователей
- Включение всех API роутеров

Pitfalls:
- Переменные окружения должны быть корректно заданы для production
- Структура папок создаётся при каждом запуске
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.future import select

from audioscribetranslate.core.files import create_uploaded_files_structure
from audioscribetranslate.db.session import AsyncSessionLocal
from audioscribetranslate.db.utils import create_admin_if_not_exists
from audioscribetranslate.models.user import User
from audioscribetranslate.routers import (
    audio_file,
    example,
    monitoring,
    summary,
    transcript,
    translation,
    user,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Жизненный цикл приложения: startup/shutdown.

    На старте:
        - Создаёт администратора, если не существует
        - Создаёт структуру папок uploaded_files/{model}/{user}
    На завершении: (можно добавить логику shutdown)

    Args:
        _app (FastAPI): Экземпляр приложения

    Yields:
        None

    Pitfalls:
        - Ошибки при создании структуры файлов не логируются
        - Администратор создаётся с дефолтным паролем, если не задано
    """
    # --- startup ---
    admin_name = os.getenv("ADMIN_NAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    async with AsyncSessionLocal() as session:
        await create_admin_if_not_exists(admin_name, admin_password, session)

    # --- create uploaded_files/{model}/{user} structure ---
    models = os.getenv("WHISPER_MODELS", "base,small,medium,large").split(",")
    models = [m.strip() for m in models if m.strip()]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.name))
        user_names = [row[0] for row in result.all()]
    create_uploaded_files_structure(models, user_names)

    yield
    # --- shutdown ---
    # Здесь можно добавить логику очистки ресурсов


app = FastAPI(title="AudioScribeTranslate API", lifespan=lifespan)


@app.get("/", response_model=dict)
def read_root() -> dict[str, str]:
    """
    Корневой эндпоинт для проверки работоспособности API.

    Returns:
        dict: Сообщение о статусе сервера

    Example:
        GET /
    """
    return {"message": "AudioScribeTranslate backend is running!"}


# Включаем все роутеры API
app.include_router(example.router)
app.include_router(user.router)
app.include_router(audio_file.router)
app.include_router(transcript.router)
app.include_router(translation.router)
app.include_router(summary.router)
app.include_router(monitoring.router)
