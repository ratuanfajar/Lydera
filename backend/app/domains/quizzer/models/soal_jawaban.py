from datetime import datetime
from typing import List, Optional

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class SoalJawaban(Base):
    __tablename__ = "soal_jawaban"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    soal_id: Mapped[int] = mapped_column(ForeignKey("soal.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    selected_option: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(nullable=False)
    # created_at (dari Base/TimestampMixin) merangkap sebagai waktu submit -- tidak perlu kolom sendiri.

    # Diisi belakangan oleh Chain 5 (evaluate_scratchwork), hanya untuk jawaban salah --
    # evaluated_at null berarti belum dievaluasi, terisi berarti hasil final (tidak dipanggil ulang).
    divergence_step: Mapped[Optional[int]] = mapped_column(Integer)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text)
    personalized_justification: Mapped[Optional[str]] = mapped_column(Text)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("soal_id", "student_id", name="uq_soal_jawaban_student"),
        Index("ix_soal_jawaban_student_soal", "student_id", "soal_id"),
        Index(
            "ix_soal_jawaban_pending_eval",
            "student_id",
            "soal_id",
            postgresql_where=text("is_correct = FALSE AND evaluated_at IS NULL"),
        ),
        CheckConstraint("selected_option IN ('A', 'B', 'C', 'D')", name="check_soal_jawaban_option"),
    )

    # Relationships
    soal: Mapped["Soal"] = relationship(back_populates="jawaban")
    langkah: Mapped[List["SoalJawabanLangkah"]] = relationship(back_populates="jawaban", cascade="all, delete-orphan")
