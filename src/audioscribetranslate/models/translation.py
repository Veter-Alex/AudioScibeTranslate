from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Translation(Base):
    """
    Модель для хранения переводов транскриптов.

    Attributes:
        id (int): Уникальный идентификатор перевода.
        transcript_id (int): ID транскрипта.
        source_language (str): Язык исходного текста.
        target_language (str): Язык перевода.
        model_name (str): Название модели перевода.
        status (str): Статус обработки: processing, done, failed.
        text (str): Текст перевода.
        processing_seconds (float): Время обработки (сек).
        text_chars (int): Количество символов в тексте.
        created_at (datetime): Время создания.
        updated_at (datetime): Время обновления.
        transcript (Transcript): Связанный транскрипт.
        summaries (List[Summary]): Список саммари перевода.

    Example:
        translation = Translation(transcript_id=1, target_language='en', ...)

    Pitfalls:
        - Статус должен обновляться при обработке.
        - Связь с Transcript и Summary должна быть корректно настроена.
    """
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True)
    transcript_id = Column(
        Integer,
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_language = Column(String, nullable=True)
    target_language = Column(String, nullable=False)
    model_name = Column(String, nullable=True)
    status = Column(String, default="processing", server_default="processing", nullable=False)  # processing|done|failed

    def __init__(self, **kwargs: Any) -> None:
        if "status" not in kwargs:
            kwargs["status"] = "processing"
        super().__init__(**kwargs)
    text = Column(Text, nullable=True)
    # Метрики
    processing_seconds = Column(Float, nullable=True)
    text_chars = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transcript = relationship(
        "Transcript", back_populates="translations", lazy="selectin"
    )
    summaries = relationship(
        "Summary",
        back_populates="translation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
