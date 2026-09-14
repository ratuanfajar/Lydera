from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.db import Base


class BlockEmbedding(Base):
    """Satu baris per chunk (bukan per block mentah -- lihat `ai-services/chatbot/chunk.py`).
    `block_ids` menyimpan block mana saja yang tergabung dalam chunk ini, dipakai untuk melacak
    balik ke `blocks` asal saat menyusun evidence/citation."""

    __tablename__ = "block_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    block_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    heading: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=False)
    kb_version: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_block_embeddings_chapter", "chapter_id", "kb_version"),
    )
