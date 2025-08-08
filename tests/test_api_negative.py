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
async def test_create_translation_missing_transcript():
    """POST /translations with non-existent transcript -> 400"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/translations/", json={"transcript_id": 9999, "target_language": "en"}
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_summary_translation_not_done(db_session: AsyncSession):
    """Summary request when translation status != done -> 400"""
    # Prepare user + transcript + translation (processing)
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
        resp = await client.post(
            "/summaries/",
            json={"translation_id": translation_id, "target_language": "en"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_transcripts_filters(db_session: AsyncSession):
    """Two audio uploads -> two transcripts -> filter by audio_file_id."""
    # Create user
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
        filtered = await client.get(f"/transcripts/?audio_file_id={target_id}")
        assert filtered.status_code == 200
        data_filtered = filtered.json()
        assert data_filtered["total"] >= 1
        assert all(item["audio_file_id"] == target_id for item in data_filtered["items"])  # type: ignore
        assert all(item["audio_file_id"] == target_id for item in data_filtered["items"])  # type: ignore
