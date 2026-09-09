from datetime import datetime
from typing import List, Optional
from app.core.db import Base
from sqlalchemy import (
    String, Integer, Text, CHAR, ForeignKey, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    reading_order: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    readable_text: Mapped[str] = mapped_column(Text, nullable=False)
    review_priority: Mapped[str] = mapped_column(Text, nullable=False, server_default='normal')
    heading_level: Mapped[Optional[int]] = mapped_column(Integer)
    source_markup: Mapped[Optional[str]] = mapped_column(Text)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    image_file: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("block_type IN ('heading', 'text', 'formula', 'table', 'image')", name="check_block_type"),
        CheckConstraint("review_priority IN ('low', 'normal', 'high')", name="check_block_review_priority"),
        Index("ix_block_chapter_order", "chapter_id", "reading_order"),
    )

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="blocks")