from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Transcript(Base):
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
    status = Column(String, default="processing")  # processing|done|failed
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
