from typing import List, Optional
from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class Soal(Base):
    __tablename__ = "soal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_request_id: Mapped[int] = mapped_column(ForeignKey("quiz_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    stimulus_id: Mapped[Optional[int]] = mapped_column(ForeignKey("soal_stimulus.id", ondelete="CASCADE"), index=True)
    bloom_level: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    kesimpulan: Mapped[str] = mapped_column(Text, nullable=False)
    source_reading_order_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reading_order_end: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default='pending')
    review_priority: Mapped[str] = mapped_column(Text, nullable=False, server_default='normal')
    validation_notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("bloom_level BETWEEN 1 AND 6", name="check_soal_bloom"),
        CheckConstraint("correct_option IN ('A', 'B', 'C', 'D')", name="check_soal_correct_opt"),
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected', 'edited')", name="check_soal_review"),
        CheckConstraint("review_priority IN ('low', 'normal', 'high')", name="check_soal_priority"),
    )

    # Relationships
    quiz_request: Mapped["QuizRequest"] = relationship(back_populates="soals")
    stimulus: Mapped[Optional["SoalStimulus"]] = relationship(back_populates="soals")
    opsi: Mapped[List["SoalOpsi"]] = relationship(back_populates="soal", cascade="all, delete-orphan")
    langkah: Mapped[List["SoalLangkah"]] = relationship(back_populates="soal", cascade="all, delete-orphan")