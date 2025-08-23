from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Summary(Base):
    """
    Модель для хранения саммари перевода.

    Attributes:
        id (int): Уникальный идентификатор саммари.
        source_translation_id (int): ID перевода, для которого создана саммари.
        base_language (str): Язык исходного текста.
        target_language (str): Язык итоговой саммари.
        model_name (str): Название модели суммаризации.
        status (str): Статус обработки: processing, done, failed.
        text (str): Текст саммари.
        created_at (datetime): Время создания.
        updated_at (datetime): Время обновления.
        translation (Translation): Связанный объект перевода.

    Example:
        summary = Summary(source_translation_id=1, target_language='ru', ...)

    Pitfalls:
        - Статус должен обновляться при обработке.
        - Связь с Translation должна быть корректно настроена.
    """
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    source_translation_id = Column(
        Integer,
        ForeignKey("translations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_language = Column(
        String, nullable=True
    )  # язык текста, который суммаризировали
    target_language = Column(String, nullable=False)  # язык итоговой саммари
    model_name = Column(String, nullable=True)
    status = Column(String, default="processing", server_default="processing", nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        if "status" not in kwargs:
            kwargs["status"] = "processing"
        super().__init__(**kwargs)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    translation = relationship(
        "Translation", back_populates="summaries", lazy="selectin"
    )
