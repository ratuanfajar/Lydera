from datetime import datetime
from enum import Enum
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Enum as SQLEnum, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

class QuizReviewStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class QuizProgress(Base):
    __tablename__ = "quiz_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_request_id: Mapped[int] = mapped_column(ForeignKey("quiz_requests.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_done: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    review_status: Mapped[QuizReviewStatus] = mapped_column(
        SQLEnum(QuizReviewStatus, native_enum=False, length=20),
        nullable=False,
        default=QuizReviewStatus.PENDING,
    )
    review_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("quiz_request_id", "student_id", name="uq_quiz_progress_quiz_student"),
        Index("ix_quiz_progress_student_id", "student_id"),
        Index("ix_quiz_progress_sse_check", "quiz_request_id", "student_id", "is_done"),
        Index(
            "ix_quiz_progress_stuck_processing",
            "review_status",
            "started_at",
            postgresql_where=text("review_status IN ('PROCESSING', 'FAILED')"),
        ),
        CheckConstraint(
            "review_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')",
            name="check_quiz_progress_review_status",
        ),
    )

    # Relationships
    quiz_request: Mapped["QuizRequest"] = relationship(back_populates="quiz_progress")
    student: Mapped["Student"] = relationship(back_populates="quiz_progress")
    