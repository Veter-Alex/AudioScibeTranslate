from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Translation(Base):
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
    status = Column(String, default="processing")  # processing|done|failed
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
