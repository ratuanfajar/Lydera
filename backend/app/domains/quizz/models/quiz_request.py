from typing import List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class QuizRequest(Base):
    __tablename__ = "quiz_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='queued')
    error: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="check_quiz_req_status"),
        Index("ix_quiz_request_status", "status", "id"),
    )

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="quiz_requests")
    # hots_count/lots_count ditentukan per bab (guru menentukan sendiri alokasinya tiap bab), bukan
    # satu angka gabungan untuk seluruh request -- makanya butuh association object
    # (QuizRequestChapter) yang punya kolom sendiri, bukan `secondary=` biasa.
    chapter_links: Mapped[List["QuizRequestChapter"]] = relationship(
        back_populates="quiz_request", cascade="all, delete-orphan"
    )
    soals: Mapped[List["Soal"]] = relationship(back_populates="quiz_request", cascade="all, delete-orphan")
    stimulus: Mapped[List["SoalStimulus"]] = relationship(back_populates="quiz_request", cascade="all, delete-orphan")