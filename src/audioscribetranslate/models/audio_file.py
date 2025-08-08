from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from . import user  # Импортируем модель User для корректной работы ForeignKey
from .base import Base


class AudioFile(Base):
    """
    Модель для хранения информации об аудиофайлах, загруженных пользователями.
    Каждая запись соответствует одному аудиофайлу и содержит метаданные,
    необходимые для хранения, обработки и последующей транскрибации.
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
        String, default="uploaded"
    )  # Статус обработки: uploaded, processing, done, failed
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
