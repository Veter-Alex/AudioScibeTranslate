import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql import ColumnElement

from audioscribetranslate.core.config import get_settings
from audioscribetranslate.core.files import get_uploaded_files_dir
from audioscribetranslate.core.tasks import enqueue_audio_chain, enqueue_transcription
from audioscribetranslate.db.session import get_db
from audioscribetranslate.models.audio_file import AudioFile

router = APIRouter(prefix="/audio_files", tags=["audio_files"])


class WhisperModelEnum(str, Enum):
    """
    Перечисление поддерживаемых моделей Whisper для выпадающего списка в Swagger UI.
    Значения должны соответствовать переменной окружения WHISPER_MODELS.
    """

    base = "base"
    small = "small"
    medium = "medium"
    large = "large"


@router.post("/", response_model=dict)
async def upload_audio_file(
    file: UploadFile = File(...),
    whisper_model: WhisperModelEnum = Form(
        ..., description="Название модели Whisper для транскрибации"
    ),
    user_id: int = Form(..., description="ID пользователя, загрузившего файл"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Загружает аудиофайл, валидирует выбранную модель Whisper и сохраняет запись в БД.

    Args:
        file (UploadFile): Загружаемый аудиофайл.
        whisper_model (WhisperModelEnum): Модель Whisper для транскрибации.
        user_id (int): ID пользователя.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Информация о загруженном файле.

    Example:
        POST /audio_files с multipart/form-data

    Pitfalls:
        - Проверяйте доступность модели Whisper.
        - Файл сохраняется на диск, убедитесь в наличии прав.
    """
    settings = get_settings()
    allowed_models = settings.whisper_models_list
    if whisper_model not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимая модель Whisper: {whisper_model}. Доступные: {allowed_models}",
        )

    # Пример: сохраняем файл на диск (можно заменить на S3 или другое хранилище)
    import os
    import uuid

    # Проверяем пользователя
    user_row = await db.execute(
        select(AudioFile.user_id).where(AudioFile.user_id == user_id)
    )
    # Получаем имя пользователя (нужно для структуры директорий)
    from audioscribetranslate.models.user import User

    user_result = await db.execute(select(User).where(User.id == user_id))
    user_obj = user_result.scalar_one_or_none()
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")

    # Путь: uploaded_files/<model>/<user_name>/
    base_dir = get_uploaded_files_dir()
    target_dir = os.path.join(base_dir, whisper_model.value, user_obj.name)
    os.makedirs(target_dir, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    relative_storage_path = f"{whisper_model.value}/{user_obj.name}/{unique_filename}"
    file_path = os.path.join(base_dir, relative_storage_path)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    audio = AudioFile(
        user_id=user_id,
        filename=unique_filename,
        original_name=file.filename,
        content_type=file.content_type,
        size=os.path.getsize(file_path),
        whisper_model=whisper_model,
        status="uploaded",
        storage_path=relative_storage_path,
    )
    db.add(audio)
    await db.commit()
    await db.refresh(audio)
    # Помещаем задачу в очередь на обработку (не блокируя ответ)
    from fastapi.concurrency import run_in_threadpool

    settings = get_settings()
    
    # Выбираем тип обработки: цепочки или отдельные задачи
    if settings.enable_processing_chains:
        # Используем новую систему цепочек обработки
        enqueue_ok = await run_in_threadpool(enqueue_audio_chain, int(audio.id), "ru")
        processing_type = "chain"
    else:
        # Используем старую систему отдельных задач
        enqueue_ok = await run_in_threadpool(enqueue_transcription, int(audio.id))
        processing_type = "transcription_only"
        
    if enqueue_ok:
        setattr(audio, "status", "queued")
        await db.commit()
        await db.refresh(audio)
    return {
        "id": audio.id,
        "filename": audio.filename,
        "relative_path": relative_storage_path,
        "whisper_model": audio.whisper_model,
        "status": audio.status if enqueue_ok else "queue_failed",
        "processing_type": processing_type if enqueue_ok else None,
    }


@router.get("/", response_model=dict)
async def list_audio_files(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    whisper_model: Optional[str] = None,
    q: Optional[str] = None,
    order_by: str = "upload_time",
    order_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Получает список аудиофайлов с фильтрами и пагинацией.

    Args:
        db (AsyncSession): Сессия базы данных.
        user_id (Optional[int]): Фильтр по пользователю.
        status (Optional[str]): Фильтр по статусу.
        whisper_model (Optional[str]): Фильтр по модели.
        q (Optional[str]): Поиск по имени файла.
        order_by (str): Поле сортировки.
        order_dir (str): Направление сортировки.
        limit (int): Лимит.
        offset (int): Смещение.

    Returns:
        dict: {items, total, limit, offset}

    Example:
        GET /audio_files?user_id=1&limit=10

    Pitfalls:
        - Лимит не может превышать 100.
        - Сортировка только по разрешённым полям.
    """
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(AudioFile)
    count_stmt = select(func.count(AudioFile.id))

    conditions = []
    if user_id is not None:
        conditions.append(AudioFile.user_id == user_id)
    if status is not None:
        conditions.append(AudioFile.status == status)
    if whisper_model is not None:
        conditions.append(AudioFile.whisper_model == whisper_model)
    if q:
        like = f"%{q}%"
        conditions.append(AudioFile.original_name.ilike(like))
    if conditions:
        for c in conditions:
            stmt = stmt.where(c)
            count_stmt = count_stmt.where(c)

    order_map: Dict[str, ColumnElement[Any]] = {
        "id": AudioFile.id,
        "upload_time": AudioFile.upload_time,
        "size": AudioFile.size,
        "whisper_model": AudioFile.whisper_model,
        "status": AudioFile.status,
    }
    if order_by not in order_map:
        order_col: ColumnElement[Any] = AudioFile.upload_time  # fallback to a valid column
    else:
        order_col = order_map[order_by]
    direction = desc if order_dir.lower() == "desc" else asc
    stmt = stmt.order_by(direction(order_col))

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": f.id,
            "filename": f.filename,
            "status": f.status,
            "whisper_model": f.whisper_model,
            "user_id": f.user_id,
            "size": f.size,
            "upload_time": f.upload_time,
        }
        for f in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{audio_file_id}", response_model=dict)
async def get_audio_file(
    audio_file_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Получает информацию об аудиофайле по ID.

    Args:
        audio_file_id (int): ID аудиофайла.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Информация о файле.

    Raises:
        HTTPException: Если файл не найден.
    """
    result = await db.execute(select(AudioFile).where(AudioFile.id == audio_file_id))
    audio_file = result.scalar_one_or_none()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return {
        "id": audio_file.id,
        "filename": audio_file.filename,
        "status": audio_file.status,
    }


@router.delete("/{audio_file_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_audio_file(
    audio_file_id: int, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Удаляет аудиофайл по id: удаляет запись из БД и сам файл с диска (если найден).

    Args:
        audio_file_id (int): ID аудиофайла.
        db (AsyncSession): Сессия базы данных.

    Returns:
        dict: Результат удаления.

    Raises:
        HTTPException: Если файл не найден.

    Pitfalls:
        - Файл на диске может отсутствовать, тогда удаляется только запись.
    """
    audio = await db.get(AudioFile, audio_file_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    # Путь к файлу
    base_dir = get_uploaded_files_dir()
    file_path = (
        os.path.join(base_dir, audio.storage_path)
        if audio.storage_path
        else os.path.join(base_dir, audio.filename)
    )
    # Удаляем файл с диска, если существует
    if os.path.exists(file_path):
        os.remove(file_path)
    # Удаляем из БД
    await db.delete(audio)
    await db.commit()
    return {"detail": f"Audio file {audio_file_id} deleted"}
