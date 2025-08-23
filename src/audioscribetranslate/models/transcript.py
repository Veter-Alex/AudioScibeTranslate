from typing import Any

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Transcript(Base):
    """
    Модель для хранения транскриптов аудиофайлов.

    Attributes:
        id (int): Уникальный идентификатор транскрипта.
        audio_file_id (int): ID аудиофайла.
        language (str): ISO код исходного языка.
        model_name (str): Название модели транскрибации.
        status (str): Статус обработки: processing, done, failed.
        text (str): Текст транскрипта.
        audio_duration_seconds (float): Длительность аудиофайла (сек).
        processing_seconds (float): Время обработки (сек).
        text_chars (int): Количество символов в тексте.
        real_time_factor (float): processing_seconds / audio_duration_seconds.
        created_at (datetime): Время создания.
        updated_at (datetime): Время обновления.
        audio_file (AudioFile): Связанный аудиофайл.
        translations (List[Translation]): Список переводов транскрипта.

    Example:
        transcript = Transcript(audio_file_id=1, language='ru', ...)

    Pitfalls:
        - Статус должен обновляться при обработке.
        - Связь с AudioFile и Translation должна быть корректно настроена.
    """
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True)
    audio_file_id = Column(
        Integer,
        ForeignKey("audio_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language = Column(String, nullable=True)  # ISO код исходного языка
    model_name = Column(String, nullable=True)
    status = Column(String, default="processing", server_default="processing", nullable=False)  # processing|done|failed

    def __init__(self, **kwargs: Any) -> None:
        if "status" not in kwargs:
            kwargs["status"] = "processing"
        super().__init__(**kwargs)
    text = Column(Text, nullable=True)
    # Метрики
    audio_duration_seconds = Column(Float, nullable=True)
    processing_seconds = Column(Float, nullable=True)
    text_chars = Column(Integer, nullable=True)
    real_time_factor = Column(
        Float, nullable=True
    )  # processing_seconds / audio_duration_seconds
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    audio_file = relationship(
        "AudioFile", back_populates="transcripts", lazy="selectin"
    )
    translations = relationship(
        "Translation",
        back_populates="transcript",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
