import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from audioscribetranslate.core.tasks import (
    enqueue_summary,
    enqueue_translation,
    summarize_translation,
    transcribe_audio,
    translate_transcript,
)
from audioscribetranslate.main import app
from audioscribetranslate.models.summary import Summary
from audioscribetranslate.models.transcript import Transcript
from audioscribetranslate.models.translation import Translation
from audioscribetranslate.models.user import User


@pytest.mark.asyncio
async def test_full_pipeline_manual(db_session: AsyncSession) -> None:
    """
    Проверяет полный ручной pipeline: upload -> transcription -> translation -> summary.

    Steps:
        - Создаёт пользователя
        - Загружает аудиофайл
        - Запускает транскрипцию
        - Проверяет создание транскрипта
        - Ставит задачу на перевод и выполняет перевод
        - Ставит задачу на summary и выполняет summary
        - Проверяет, что перевод и summary завершены успешно
    """
    # Create user
    user = User(name=f"tester_{uuid.uuid4().hex[:8]}", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    # Upload audio file
    file_content = b"dummy audio data"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/audio_files/",
            files={"file": ("sample.mp3", io.BytesIO(file_content), "audio/mpeg")},
            data={"whisper_model": "base", "user_id": str(user_id)},
        )
        assert resp.status_code == 200, resp.text
        audio_id = resp.json()["id"]

    # Directly run transcription task (simulate worker)
    transcribe_audio(audio_id)

    # Verify transcript created
    t_row = await db_session.execute(
        Transcript.__table__.select().where(Transcript.audio_file_id == audio_id)
    )
    t_first = t_row.first()
    assert t_first is not None
    transcript_id = t_first[0]

    # Enqueue translation (should succeed since transcript done)
    ok, translation_id = enqueue_translation(
        transcript_id=transcript_id, target_language="en"
    )
    assert ok and translation_id is not None

    # Run translation task
    translate_transcript(translation_id)

    # Enqueue summary
    ok2, summary_id = enqueue_summary(
        translation_id=translation_id, target_language="en"
    )
    assert ok2 and summary_id is not None

    # Run summary task
    summarize_translation(summary_id)

    # Final assertions
    tr = await db_session.get(Translation, translation_id)
    sm = await db_session.get(Summary, summary_id)
    assert tr and tr.text and tr.status == "done"
    assert sm and sm.text and sm.status == "done"
