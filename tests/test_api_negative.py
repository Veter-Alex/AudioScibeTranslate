import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.core.tasks import transcribe_audio
from audioscribetranslate.main import app
from audioscribetranslate.models.audio_file import AudioFile
from audioscribetranslate.models.transcript import Transcript
from audioscribetranslate.models.translation import Translation
from audioscribetranslate.models.user import User


@pytest.mark.asyncio
async def test_create_translation_missing_transcript() -> None:
    """
    Проверяет обработку запроса на создание перевода с несуществующим transcript_id.
    Бизнес-значимость: предотвращает появление "висящих" переводов без исходных данных.
    Фикстуры: нет, используется чистый тестовый клиент.
    Ожидаемое поведение: 400 Bad Request, детализированное сообщение об ошибке.
    Граничные условия: transcript_id не существует, тип не int, пустое значение.
    Исключения: ValueError, HTTPException.
    """
    # Setup: используем ASGITransport для изоляции теста
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Execution: отправляем запрос с несуществующим transcript_id
        resp = await client.post(
            "/translations/", json={"transcript_id": 9999, "target_language": "en"}
        )
        # Verification: проверяем статус и структуру ошибки
        assert resp.status_code == 400
        # Проверяем, что ошибка содержит ожидаемое сообщение
        assert "transcript not ready" in resp.text or "internal error" in resp.text
        # Edge-case: невалидный тип transcript_id
        resp2 = await client.post(
            "/translations/", json={"transcript_id": "not_an_int", "target_language": "en"}
        )
        assert resp2.status_code in (400, 422)
        # Edge-case: пустое значение transcript_id
        resp3 = await client.post(
            "/translations/", json={"target_language": "en"}
        )
        assert resp3.status_code in (400, 422)
        # Что сломается при изменении: если API начнет возвращать 200 для несуществующего transcript_id,
        # появятся "висящие" переводы, нарушится инвариант целостности данных.


@pytest.mark.asyncio
async def test_create_summary_translation_not_done(db_session: AsyncSession) -> None:
    """
    Проверяет, что запрос на summary при статусе перевода != done возвращает 400.
    Бизнес-значимость: summary не должен создаваться для незавершённого перевода.
    Фикстуры: создаются пользователь, аудиофайл, транскрипт, перевод (status=processing).
    Ожидаемое поведение: 400 Bad Request.
    Граничные условия: translation_id не существует, тип не int, пустое значение.
    Исключения: ValueError, HTTPException.
    """
    # Setup: создаём пользователя, аудиофайл, транскрипт, перевод (status=processing)
    user = User(name=f"u1_{uuid.uuid4().hex[:8]}", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    audio = AudioFile(
        user_id=user.id,
        filename="f1.mp3",
        original_name="f1.mp3",
        content_type="audio/mpeg",
        size=3,
        whisper_model="base",
        status="done",
        storage_path=f"base/{user.id}/f1.mp3",
    )
    db_session.add(audio)
    await db_session.commit()
    await db_session.refresh(audio)
    transcript = Transcript(audio_file_id=audio.id, status="done")
    db_session.add(transcript)
    await db_session.commit()
    await db_session.refresh(transcript)
    translation = Translation(
        transcript_id=transcript.id,
        target_language="en",
        status="processing",
    )
    db_session.add(translation)
    await db_session.commit()
    await db_session.refresh(translation)
    translation_id = translation.id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Execution: пытаемся создать summary для незавершённого перевода
        resp = await client.post(
            "/summaries/",
            json={"translation_id": translation_id, "target_language": "en"},
        )
        # Verification: ожидаем ошибку 400
        assert resp.status_code == 400
        # Edge-case: невалидный тип translation_id
        resp2 = await client.post(
            "/summaries/",
            json={"translation_id": "not_an_int", "target_language": "en"},
        )
        assert resp2.status_code in (400, 422)
        # Edge-case: пустое значение translation_id
        resp3 = await client.post(
            "/summaries/",
            json={"target_language": "en"},
        )
        assert resp3.status_code in (400, 422)
        # Что сломается при изменении: если API начнет возвращать 200 для незавершённого перевода,
        # появятся некорректные summary, нарушится бизнес-логика.


@pytest.mark.asyncio
async def test_list_transcripts_filters(db_session: AsyncSession) -> None:
    """
    Проверяет фильтрацию транскриптов по audio_file_id.
    Бизнес-значимость: корректная фильтрация позволяет получать только релевантные транскрипты.
    Фикстуры: создаётся пользователь, два аудиофайла, транскрипция.
    Ожидаемое поведение: все результаты соответствуют фильтру.
    Граничные условия: несуществующий audio_file_id, пустой список.
    Исключения: ValueError, HTTPException.
    """
    # Setup: создаём пользователя
    user = User(name=f"userf_{uuid.uuid4().hex[:8]}", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id
    # Upload two files and run transcription
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created_ids: list[int] = []
        for _ in range(2):
            resp = await client.post(
                "/audio_files/",
                files={"file": ("a.mp3", io.BytesIO(b"data"), "audio/mpeg")},
                data={"whisper_model": "base", "user_id": str(user_id)},
            )
            assert resp.status_code == 200
            aid = resp.json()["id"]
            created_ids.append(aid)
            transcribe_audio(aid)
        target_id = created_ids[0]
        # Execution: фильтруем транскрипты по первому audio_file_id
        filtered = await client.get(f"/transcripts/?audio_file_id={target_id}")
        assert filtered.status_code == 200
        data_filtered = filtered.json()
        assert data_filtered["total"] >= 1
        # Verification: все результаты соответствуют фильтру
        assert all(item["audio_file_id"] == target_id for item in data_filtered["items"])
        # Edge-case: несуществующий audio_file_id
        filtered_none = await client.get(f"/transcripts/?audio_file_id=999999")
        assert filtered_none.status_code == 200
        data_none = filtered_none.json()
        assert data_none["total"] == 0
        # Edge-case: невалидный тип audio_file_id
        filtered_invalid = await client.get(f"/transcripts/?audio_file_id=not_an_int")
        assert filtered_invalid.status_code in (400, 422)
        # Что сломается при изменении: если фильтрация не работает, пользователь получит нерелевантные данные.
