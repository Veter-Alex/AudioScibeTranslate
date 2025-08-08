from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.db.session import get_db

router = APIRouter()


@router.get("/ping")
async def ping(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    # Пример использования db: можно выполнить любой SQL-запрос
    await db.execute(text("SELECT 1"))  # Используем db, чтобы избежать предупреждения
    return {"message": "pong"}
