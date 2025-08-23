"""
:module: src/audioscribetranslate/models/transcript.py
Тесты модели транскрипта.
Требования: TRANSCRIPT-101, TRANSCRIPT-102
"""
import pytest

from src.audioscribetranslate.models.transcript import Transcript


def test_transcript_model_fields() -> None:
    """Happy path: поля модели Transcript соответствуют требованиям (TRANSCRIPT-101)"""
    transcript = Transcript(
        audio_file_id=1,
        language="ru",
        model_name="base",
        status="done",
        text="Пример текста",
        audio_duration_seconds=10.5,
        processing_seconds=2.5,
        text_chars=12,
        real_time_factor=0.24
    )
    assert transcript.audio_file_id == 1
    assert transcript.language == "ru"
    assert transcript.model_name == "base"
    assert transcript.status == "done"
    assert transcript.text == "Пример текста"
    assert transcript.audio_duration_seconds == 10.5
    assert transcript.processing_seconds == 2.5
    assert transcript.text_chars == 12
    assert transcript.real_time_factor == 0.24

def test_transcript_model_default_status() -> None:
    """Edge case: статус по умолчанию — processing (TRANSCRIPT-102)"""
    transcript = Transcript(audio_file_id=2)
    assert transcript.status == "processing"

def test_transcript_model_relationships() -> None:
    """Негативный тест: audio_file и translations — ORM связи (TRANSCRIPT-102, баг #88)"""
    assert hasattr(Transcript, "audio_file")
    assert hasattr(Transcript, "translations")
    assert hasattr(Transcript, "audio_file")
    assert hasattr(Transcript, "translations")
