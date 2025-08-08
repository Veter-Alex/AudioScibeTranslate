from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.db.session import get_db
from audioscribetranslate.models.transcript import Transcript

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("/", response_model=dict)
async def list_transcripts(
    db: AsyncSession = Depends(get_db),
    audio_file_id: Optional[int] = None,
    status: Optional[str] = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(Transcript)
    count_stmt = select(func.count(Transcript.id))

    if audio_file_id is not None:
        stmt = stmt.where(Transcript.audio_file_id == audio_file_id)
        count_stmt = count_stmt.where(Transcript.audio_file_id == audio_file_id)
    if status is not None:
        stmt = stmt.where(Transcript.status == status)
        count_stmt = count_stmt.where(Transcript.status == status)

    order_map = {
        "id": Transcript.id,
        "created_at": Transcript.created_at,
        "updated_at": Transcript.updated_at,
        "status": Transcript.status,
    }
    order_col = order_map.get(order_by, Transcript.created_at)
    direction_fn = desc if order_dir.lower() == "desc" else asc
    order_col_any: Any = order_col  # help type checker
    stmt = stmt.order_by(direction_fn(order_col_any)).offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()

    items = [
        {
            "id": r.id,
            "audio_file_id": r.audio_file_id,
            "status": r.status,
            "language": r.language,
            "model_name": r.model_name,
            "has_text": r.text is not None,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{transcript_id}", response_model=dict)
async def get_transcript(
    transcript_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    res = await db.execute(select(Transcript).where(Transcript.id == transcript_id))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {
        "id": obj.id,
        "audio_file_id": obj.audio_file_id,
        "status": obj.status,
        "language": obj.language,
        "model_name": obj.model_name,
        "text": obj.text,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
    }
