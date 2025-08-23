from typing import Any, Optional, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.core.tasks import enqueue_translation
from audioscribetranslate.db.session import get_db
from audioscribetranslate.models.translation import Translation

router = APIRouter(prefix="/translations", tags=["translations"])


@router.get("/", response_model=dict)
async def list_translations(
    db: AsyncSession = Depends(get_db),
    transcript_id: Optional[int] = None,
    status: Optional[str] = None,
    target_language: Optional[str] = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Получить список переводов с фильтрами и пагинацией.

    Args:
        db (AsyncSession): Сессия базы данных.
        transcript_id (Optional[int]): Фильтр по транскрипту.
        status (Optional[str]): Фильтр по статусу.
        target_language (Optional[str]): Фильтр по целевому языку.
        order_by (str): Поле сортировки.
        order_dir (str): Направление сортировки.
        limit (int): Лимит.
        offset (int): Смещение.

    Returns:
        dict: {items, total, limit, offset}

    Example:
        GET /translations?transcript_id=1&limit=10

    Pitfalls:
        - Лимит не может превышать 100.
        - Сортировка только по разрешённым полям.
    """
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(Translation)
    count_stmt = select(func.count(Translation.id))

    if transcript_id is not None:
        stmt = stmt.where(Translation.transcript_id == transcript_id)
        count_stmt = count_stmt.where(Translation.transcript_id == transcript_id)
    if status is not None:
        stmt = stmt.where(Translation.status == status)
        count_stmt = count_stmt.where(Translation.status == status)
    if target_language is not None:
        stmt = stmt.where(Translation.target_language == target_language)
        count_stmt = count_stmt.where(Translation.target_language == target_language)

    from sqlalchemy.sql.schema import Column

    order_col: Column[Any]
    if order_by == "id":
        order_col = Translation.id
    elif order_by == "updated_at":
        order_col = Translation.updated_at
    elif order_by == "status":
        order_col = Translation.status
    elif order_by == "target_language":
        order_col = Translation.target_language
    else:
        order_col = Translation.created_at
    direction_fn = desc if order_dir.lower() == "desc" else asc
    stmt = stmt.order_by(direction_fn(order_col)).offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        {
            "id": r.id,
            "transcript_id": r.transcript_id,
            "status": r.status,
            "source_language": r.source_language,
            "target_language": r.target_language,
            "model_name": r.model_name,
            "has_text": r.text is not None,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{translation_id}", response_model=dict)
async def get_translation(
    translation_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Получить информацию о переводе по ID.

    Args:
        translation_id (int): ID перевода.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Информация о переводе.

    Raises:
        HTTPException: Если перевод не найден.
    """
    res = await db.execute(select(Translation).where(Translation.id == translation_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Translation not found")
    return {
        "id": obj.id,
        "transcript_id": obj.transcript_id,
        "status": obj.status,
        "source_language": obj.source_language,
        "target_language": obj.target_language,
        "model_name": obj.model_name,
        "text": obj.text,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }


class TranslationCreateRequest(BaseModel):
    """
    Модель запроса на создание перевода.

    Attributes:
        transcript_id (int): ID транскрипта.
        target_language (str): Целевой язык.
        model_name (Optional[str]): Название модели.
    """
    transcript_id: int = Field(..., ge=1)
    target_language: str = Field(..., min_length=1, max_length=16)
    model_name: Optional[str] = Field(None, max_length=100)


@router.post("/", response_model=dict, status_code=201)
async def create_translation(payload: TranslationCreateRequest) -> dict[str, Any]:
    """
    Поставить задачу на создание перевода.

    Args:
        payload (TranslationCreateRequest): Данные для создания перевода.

    Returns:
        dict: ID созданного перевода и статус постановки в очередь.

    Raises:
        HTTPException: Если транскрипт не готов или внутренняя ошибка.

    Example:
        POST /translations
    """
    ok, translation_id = enqueue_translation(
        payload.transcript_id, payload.target_language, payload.model_name
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Unable to enqueue translation (transcript not ready or internal error)",
        )
    return {"id": translation_id, "status": "queued"}
