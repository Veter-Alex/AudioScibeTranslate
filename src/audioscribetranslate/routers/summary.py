from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.core.tasks import enqueue_summary
from audioscribetranslate.db.session import get_db
from audioscribetranslate.models.summary import Summary

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.get("/", response_model=dict)
async def list_summaries(
    db: AsyncSession = Depends(get_db),
    translation_id: Optional[int] = None,
    status: Optional[str] = None,
    target_language: Optional[str] = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(Summary)
    count_stmt = select(func.count(Summary.id))

    if translation_id is not None:
        stmt = stmt.where(Summary.source_translation_id == translation_id)
        count_stmt = count_stmt.where(Summary.source_translation_id == translation_id)
    if status is not None:
        stmt = stmt.where(Summary.status == status)
        count_stmt = count_stmt.where(Summary.status == status)
    if target_language is not None:
        stmt = stmt.where(Summary.target_language == target_language)
        count_stmt = count_stmt.where(Summary.target_language == target_language)

    from typing import Any as _Any

    order_col: _Any
    if order_by == "id":
        order_col = Summary.id
    elif order_by == "updated_at":
        order_col = Summary.updated_at
    elif order_by == "status":
        order_col = Summary.status
    elif order_by == "target_language":
        order_col = Summary.target_language
    else:
        order_col = Summary.created_at
    direction_fn = desc if order_dir.lower() == "desc" else asc
    stmt = stmt.order_by(direction_fn(order_col)).offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        {
            "id": r.id,
            "translation_id": r.source_translation_id,
            "status": r.status,
            "base_language": r.base_language,
            "target_language": r.target_language,
            "model_name": r.model_name,
            "has_text": r.text is not None,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{summary_id}", response_model=dict)
async def get_summary(
    summary_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    res = await db.execute(select(Summary).where(Summary.id == summary_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {
        "id": obj.id,
        "translation_id": obj.source_translation_id,
        "status": obj.status,
        "base_language": obj.base_language,
        "target_language": obj.target_language,
        "model_name": obj.model_name,
        "text": obj.text,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }


class SummaryCreateRequest(BaseModel):
    translation_id: int = Field(..., ge=1)
    target_language: str = Field(..., min_length=1, max_length=16)
    model_name: str | None = Field(None, max_length=100)


@router.post("/", response_model=dict, status_code=201)
async def create_summary(payload: SummaryCreateRequest) -> dict[str, Any]:
    ok, summary_id = enqueue_summary(
        payload.translation_id, payload.target_language, payload.model_name
    )
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Unable to enqueue summary (translation not ready or internal error)",
        )
    return {"id": summary_id, "status": "queued"}
