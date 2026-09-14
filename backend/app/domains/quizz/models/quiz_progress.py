from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

class QuizProgress(Base):
    __tablename__ = "quiz_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    quiz_request_id: Mapped[int] = mapped_column(ForeignKey("quiz_requests.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_done: Mapped[bool] = mapped_column(default=False)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    __table_args__ = (
        Index("ix_quiz_progress_student_request", "student_id", "quiz_request_id", unique=True),
    )

    # Relationships
    quiz_request: Mapped["QuizRequest"] = relationship(back_populates="quiz_progress")
    student: Mapped["Student"] = relationship(back_populates="quiz_progress")
    