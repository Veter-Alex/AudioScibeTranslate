from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import user  # Импортируем модель User для корректной работы ForeignKey
from .base import Base


class AudioFile(Base):
    """
    Модель для хранения информации об аудиофайлах, загруженных пользователями.

    Attributes:
        id (int): Уникальный идентификатор аудиофайла.
        user_id (int): Владелец файла (пользователь).
        filename (str): Имя файла на сервере (уникальное или с UUID).
        original_name (str): Оригинальное имя файла при загрузке.
        content_type (str): MIME-тип файла (например, audio/mpeg).
        size (int): Размер файла в байтах.
        upload_time (datetime): Время загрузки файла.
        whisper_model (str): Название модели Whisper, выбранной для транскрибации.
        status (str): Статус обработки: uploaded, processing, done, failed.
        storage_path (str): Относительный путь (model/user/filename).
        transcripts (List[Transcript]): Список транскриптов, связанных с этим файлом.

    Example:
        audio = AudioFile(filename='file.wav', user_id=1, ...)

    Pitfalls:
        - Необходимо корректно заполнять storage_path для поиска файла.
        - Статус должен обновляться при обработке.
    """

    __tablename__ = "audio_files"

    id = Column(
        Integer, primary_key=True, index=True
    )  # Уникальный идентификатор аудиофайла
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )  # Владелец файла (пользователь)
    filename = Column(
        String, nullable=False
    )  # Имя файла на сервере (уникальное или с UUID)
    original_name = Column(
        String, nullable=False
    )  # Оригинальное имя файла при загрузке
    content_type = Column(
        String, nullable=False
    )  # MIME-тип файла (например, audio/mpeg)
    size = Column(Integer, nullable=False)  # Размер файла в байтах
    upload_time = Column(
        DateTime(timezone=True), server_default=func.now()
    )  # Время загрузки файла
    whisper_model = Column(
        String, nullable=False
    )  # Название модели Whisper, выбранной для транскрибации
    status = Column(
        String, default="uploaded", server_default="uploaded", nullable=False
    )  # Статус обработки: uploaded, processing, done, failed

    def __init__(self, **kwargs: Any) -> None:
        if "status" not in kwargs:
            kwargs["status"] = "uploaded"
        super().__init__(**kwargs)
    storage_path = Column(
        String, nullable=True
    )  # Относительный путь (model/user/filename)

    # ORM relationships
    transcripts = relationship(
        "Transcript",
        back_populates="audio_file",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
