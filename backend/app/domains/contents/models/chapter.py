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
    chapter_progress: Mapped[List["ChapterProgress"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    cp: Mapped[Optional["Cp"]] = relationship(back_populates="chapters")
    blocks: Mapped[List["Block"]] = relationship(back_populates="chapter", order_by="Block.reading_order", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")

    @property
    def latest_job(self) -> "Job | None":
        return self.__dict__.get("_latest_job")

    @latest_job.setter
    def latest_job(self, value: "Job | None") -> None:
        self.__dict__["_latest_job"] = value

    @property
    def blocks_count(self) -> int | None:
        return self.__dict__.get("_blocks_count")

    @blocks_count.setter
    def blocks_count(self, value: int | None) -> None:
        self.__dict__["_blocks_count"] = value

    @property
    def is_need_review(self) -> bool:
        latest_job = self.latest_job
        if latest_job is None or latest_job.status != "done":
            return False

        if self.blocks_count is not None:
            return self.blocks_count == 0

        return len(self.blocks) == 0