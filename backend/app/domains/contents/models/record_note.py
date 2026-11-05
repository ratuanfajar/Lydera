from typing import Optional

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

class RecordNote(Base):
    __tablename__ = "record_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("ix_record_note_chapter_student", "student_id", "chapter_id", unique=True),
    )
    
    # Relationships
    chapter: Mapped["Chapter"] = relationship()
    student: Mapped["Student"] = relationship()
