from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChatMessage(Base):
    """`tool_calls` mencatat PROSES pemanggilan tool (untuk debug/audit) -- apa yang dipanggil,
    dengan argumen apa. `citations` mencatat HASIL AKHIR yang ditampilkan ke siswa (per-source
    justifikasi + evidence, setelah lolos grounding check di `citations.verify_citations`). Dua hal
    berbeda: guru bisa audit apa yang dicoba vs apa yang benar-benar disajikan sebagai bukti."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[Optional[list]] = mapped_column(JSONB)
    citations: Mapped[Optional[list]] = mapped_column(JSONB)
    scope_klass: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="check_chat_message_role"),
        Index("ix_chat_messages_session", "session_id", "id"),
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
