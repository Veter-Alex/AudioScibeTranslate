"""
:module: src/audioscribetranslate/models/summary.py
Тесты модели саммари перевода.
Требования: SUMMARY-101, SUMMARY-102
"""
import pytest

from src.audioscribetranslate.models.summary import Summary


def test_summary_model_fields() -> None:
    """Happy path: поля модели Summary соответствуют требованиям (SUMMARY-101)"""
    summary = Summary(
        source_translation_id=1,
        base_language="en",
        target_language="ru",
        model_name="base",
        status="done",
        text="Краткое содержание"
    )
    assert summary.source_translation_id == 1
    assert summary.base_language == "en"
    assert summary.target_language == "ru"
    assert summary.model_name == "base"
    assert summary.status == "done"
    assert summary.text == "Краткое содержание"

def test_summary_model_default_status() -> None:
    """Edge case: статус по умолчанию — processing (SUMMARY-102)"""
    summary = Summary(source_translation_id=2, target_language="fr")
    assert summary.status == "processing"

def test_summary_model_relationship() -> None:
    """Негативный тест: translation — ORM связь (SUMMARY-102, баг #101)"""
    assert hasattr(Summary, "translation")
    """Негативный тест: translation — ORM связь (SUMMARY-102, баг #101)"""
    assert hasattr(Summary, "translation")
