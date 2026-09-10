from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from app.core.db import Base
from datetime import datetime

class ChapterProgress(Base):
    __tablename__ = "chapters_progress"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    is_done: Mapped[bool] = mapped_column(default=False)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )

    __table_args__ = (
        Index("ix_chapter_progress_user_chapter", "student_id", "chapter_id", unique=True),
    )

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="chapter_progress")
    student: Mapped["Student"] = relationship(back_populates="chapters_progress")
