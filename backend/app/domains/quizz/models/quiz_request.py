from typing import List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class QuizRequest(Base):
    __tablename__ = "quiz_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    hots_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lots_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='queued')
    error: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("hots_count >= 0", name="check_quiz_req_hots"),
        CheckConstraint("lots_count >= 0", name="check_quiz_req_lots"),
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="check_quiz_req_status"),
        Index("ix_quiz_request_status", "status", "id"),
    )

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="quiz_requests")
    # Tabel pivot otomatis dimanage SQLAlchemy lewat secondary (lihat di bawah)
    chapters: Mapped[List["Chapter"]] = relationship(
        secondary="quiz_request_chapters",
        backref="quiz_requests"
    )
    soals: Mapped[List["Soal"]] = relationship(back_populates="quiz_request", cascade="all, delete-orphan")
    stimulus: Mapped[List["SoalStimulus"]] = relationship(back_populates="quiz_request", cascade="all, delete-orphan")