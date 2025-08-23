"""
:module: src/audioscribetranslate/models/translation.py
Тесты модели перевода транскрипта.
Требования: TRANSLATION-101, TRANSLATION-102
"""
import pytest

from src.audioscribetranslate.models.translation import Translation


def test_translation_model_fields() -> None:
    """Happy path: поля модели Translation соответствуют требованиям (TRANSLATION-101)"""
    translation = Translation(
        transcript_id=1,
        source_language="ru",
        target_language="en",
        model_name="base",
        status="done",
        text="Hello world",
        processing_seconds=1.5,
        text_chars=11
    )
    assert translation.transcript_id == 1
    assert translation.source_language == "ru"
    assert translation.target_language == "en"
    assert translation.model_name == "base"
    assert translation.status == "done"
    assert translation.text == "Hello world"
    assert translation.processing_seconds == 1.5
    assert translation.text_chars == 11

def test_translation_model_default_status() -> None:
    """Edge case: статус по умолчанию — processing (TRANSLATION-102)"""
    translation = Translation(transcript_id=2, target_language="fr")
    assert translation.status == "processing"

def test_translation_model_relationships() -> None:
    """Негативный тест: transcript и summaries — ORM связи (TRANSLATION-102, баг #99)"""
    assert hasattr(Translation, "transcript")
    assert hasattr(Translation, "summaries")
    assert hasattr(Translation, "transcript")
    assert hasattr(Translation, "summaries")
