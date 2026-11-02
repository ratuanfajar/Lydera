from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChapterKb(Base):
    """Satu baris per chapter: cuma nomor versi knowledge base saat ini.

    `kb_version` di-increment tiap reindex (guru republish bab) -- dipakai sebagai penanda embedding
    mana yang aktif di `block_embeddings` (kolom `kb_version` di situ). Tidak ada lagi anchor topik
    di sini -- scope gate sekarang pakai skor similarity retrieval langsung, bukan bandingkan ke
    anchor statis per-chapter (lihat `ai-services/chatbot/scope_gate.py`)."""

    __tablename__ = "chapter_kb"

    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True
    )
    kb_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    chapter: Mapped["Chapter"] = relationship()
