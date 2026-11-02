from typing import List

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChatSession(Base):
    """Satu sesi tanya-jawab siswa, di-scope ke CLASSROOM (bukan satu chapter) -- retrieval lewat
    pgvector otomatis nyari lintas semua chapter published di classroom ini, similarity-nya sendiri
    yang jadi sinyal scope gate (lihat `ai-services/chatbot/scope_gate.py`), jadi tidak perlu siswa
    deklarasi chapter_id mana saja secara eksplisit."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        Index("ix_chat_sessions_student_classroom", "student_id", "classroom_id"),
    )

    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )
