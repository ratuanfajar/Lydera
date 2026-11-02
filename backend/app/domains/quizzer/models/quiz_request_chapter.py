from typing import List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class QuizRequestChapter(Base):
    __tablename__ = "quiz_request_chapters"

    quiz_request_id: Mapped[int] = mapped_column(ForeignKey("quiz_requests.id", ondelete="CASCADE"), primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True)
    hots_count: Mapped[int] = mapped_column(Integer, nullable=False)
    lots_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("hots_count >= 0", name="check_quiz_req_chapter_hots"),
        CheckConstraint("lots_count >= 0", name="check_quiz_req_chapter_lots"),
    )

    # Relationships
    quiz_request: Mapped["QuizRequest"] = relationship(back_populates="chapter_links")
    chapter: Mapped["Chapter"] = relationship()