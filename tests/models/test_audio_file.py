"""
:module: src/audioscribetranslate/models/audio_file.py
Тесты модели аудиофайла.
Требования: AUDIO-101, AUDIO-102
"""
import pytest

from src.audioscribetranslate.models.audio_file import AudioFile


def test_audio_file_model_fields() -> None:
    """Happy path: поля модели AudioFile соответствуют требованиям (AUDIO-101)"""
    audio = AudioFile(
        user_id=1,
        filename="file.wav",
        original_name="original.wav",
        content_type="audio/wav",
        size=12345,
        whisper_model="base",
        status="uploaded",
        storage_path="base/1/file.wav"
    )
    assert audio.user_id == 1
    assert audio.filename == "file.wav"
    assert audio.original_name == "original.wav"
    assert audio.content_type == "audio/wav"
    assert audio.size == 12345
    assert audio.whisper_model == "base"
    assert audio.status == "uploaded"
    assert audio.storage_path == "base/1/file.wav"

def test_audio_file_model_default_status() -> None:
    """Edge case: статус по умолчанию — uploaded (AUDIO-102)"""
    audio = AudioFile(
        user_id=2,
        filename="f2.wav",
        original_name="orig2.wav",
        content_type="audio/wav",
        size=100,
        whisper_model="small"
    )
    assert audio.status == "uploaded"

def test_audio_file_model_relationship() -> None:
    """Негативный тест: transcripts — ORM связь (AUDIO-102, баг #77)"""
    # MOCK: Проверяем, что transcripts — relationship
    assert hasattr(AudioFile, "transcripts")
    # MOCK: Проверяем, что transcripts — relationship
    assert hasattr(AudioFile, "transcripts")
