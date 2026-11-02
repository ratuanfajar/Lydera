from typing import List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class SoalStimulus(Base):
    __tablename__ = "soal_stimulus"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_request_id: Mapped[int] = mapped_column(ForeignKey("quiz_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    source_markup: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    readable_text: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default='pending')
    source_reading_order_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reading_order_end: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected', 'edited')", name="check_stimulus_review"),
    )

    # Relationships
    quiz_request: Mapped["QuizRequest"] = relationship(back_populates="stimulus")
    soals: Mapped[List["Soal"]] = relationship(back_populates="stimulus")