from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Summary(Base):
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
    status = Column(String, default="processing")
    text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    translation = relationship(
        "Translation", back_populates="summaries", lazy="selectin"
    )
