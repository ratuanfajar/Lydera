from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base
from sqlalchemy import Enum as SQLEnum

class QuizRequestStatus(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"

class QuizRequest(Base):
    __tablename__ = "quiz_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255))
    status_published: Mapped[QuizRequestStatus] = mapped_column(
        SQLEnum(QuizRequestStatus, native_enum=False, length=20),
        nullable=False,
        default=QuizRequestStatus.DRAFT,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='queued')
    error: Mapped[Optional[str]] = mapped_column(Text)

    max_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="check_quiz_req_status"),
        Index("ix_quiz_request_status", "status", "id"),
    )

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="quiz_requests")
    classroom: Mapped["Classroom"] = relationship(back_populates="quiz_requests")
    quiz_progress: Mapped["QuizProgress"] = relationship(back_populates="quiz_request")
    # hots_count/lots_count ditentukan per bab (guru menentukan sendiri alokasinya tiap bab), bukan
    # satu angka gabungan untuk seluruh request -- makanya butuh association object
    # (QuizRequestChapter) yang punya kolom sendiri, bukan `secondary=` biasa.
    chapter_links: Mapped[List["QuizRequestChapter"]] = relationship(
        back_populates="quiz_request", cascade="all, delete-orphan"
    )
    soals: Mapped[List["Soal"]] = relationship(back_populates="quiz_request", order_by="Soal.id", cascade="all, delete-orphan")
    stimulus: Mapped[List["SoalStimulus"]] = relationship(back_populates="quiz_request",order_by="QuizRequestChapter.chapter_id", cascade="all, delete-orphan")