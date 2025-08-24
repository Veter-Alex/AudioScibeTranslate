import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import ColumnElement

from audioscribetranslate.core.files import get_uploaded_files_dir
from audioscribetranslate.db.session import get_db
from audioscribetranslate.models.audio_file import AudioFile
from audioscribetranslate.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=dict)
async def create_user(
    name: str,
    hashed_password: str,
    is_active: int = 1,
    is_admin: int = 0,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Создать нового пользователя.

    Args:
        name (str): Имя пользователя.
        hashed_password (str): Хэш пароля.
        is_active (int): Активен ли пользователь.
        is_admin (int): Является ли администратором.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Информация о созданном пользователе.

    Raises:
        HTTPException: Если пользователь уже существует.

    Example:
        POST /users
    """
    existing = await db.execute(select(User).where(User.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        name=name,
        hashed_password=hashed_password,
        is_active=is_active,
        is_admin=is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "id": user.id,
        "name": user.name,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
    }


@router.get("/", response_model=dict)
async def list_users(
    db: AsyncSession = Depends(get_db),
    is_active: Optional[int] = None,
    is_admin: Optional[int] = None,
    name_like: Optional[str] = None,
    order_by: str = "id",
    order_dir: str = "asc",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Получить список пользователей с фильтрами и пагинацией.

    Args:
        db (AsyncSession): Сессия базы данных.
        is_active (Optional[int]): Фильтр по активности.
        is_admin (Optional[int]): Фильтр по администратору.
        name_like (Optional[str]): Поиск по имени.
        order_by (str): Поле сортировки.
        order_dir (str): Направление сортировки.
        limit (int): Лимит.
        offset (int): Смещение.

    Returns:
        dict: {items, total, limit, offset}

    Example:
        GET /users?is_active=1&limit=10

    Pitfalls:
        - Лимит не может превышать 100.
        - Сортировка только по разрешённым полям.
    """
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(User)
    count_stmt = select(func.count(User.id))
    conditions = []
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    if is_admin is not None:
        conditions.append(User.is_admin == is_admin)
    if name_like:
        like = f"%{name_like}%"
        conditions.append(User.name.ilike(like))
    if conditions:
        for c in conditions:
            stmt = stmt.where(c)
            count_stmt = count_stmt.where(c)

    order_map: Dict[str, ColumnElement[Any]] = {"id": User.id, "name": User.name}
    order_col: ColumnElement[Any] = order_map.get(order_by, User.id)
    direction = desc if order_dir.lower() == "desc" else asc
    stmt = stmt.order_by(direction(order_col))

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": u.id,
            "name": u.name,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
        }
        for u in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{user_id}", response_model=dict)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Получить информацию о пользователе по ID.

    Args:
        user_id (int): ID пользователя.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Информация о пользователе.

    Raises:
        HTTPException: Если пользователь не найден.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "name": user.name,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
    }


@router.delete("/{user_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Удаляет пользователя по id, а также все его аудиофайлы из БД и с диска.

    Args:
        user_id (int): ID пользователя.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Результат удаления.

    Raises:
        HTTPException: Если пользователь не найден.

    Pitfalls:
        - Аудиофайлы на диске могут отсутствовать, тогда удаляется только запись.
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Удаляем все аудиофайлы пользователя
    result = await db.execute(select(AudioFile).where(AudioFile.user_id == user_id))
    files = result.scalars().all()
    for audio in files:
        file_path = os.path.join(get_uploaded_files_dir(), audio.storage_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        await db.delete(audio)
    # Удаляем пользователя
    await db.delete(user)
    await db.commit()
    return {"detail": f"User {user_id} and all their audio files deleted"}
