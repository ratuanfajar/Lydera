from datetime import datetime
from typing import List, Optional
from app.core.db import Base
from sqlalchemy import (
    String, Integer, Text, CHAR, ForeignKey, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[Optional[int]] = mapped_column(Integer)
    title: Mapped[Optional[str]] = mapped_column(Text)
    source_file: Mapped[Optional[str]] = mapped_column(Text)
    cp_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cp.id"))

    __table_args__ = (
        Index("ix_chapter_module", "module_id", "number"),
    )

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="chapters")
    chapter_progress: Mapped["ChapterProgress"] = relationship(back_populates="chapter")
    cp: Mapped[Optional["Cp"]] = relationship(back_populates="chapters")
    blocks: Mapped[List["Block"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")