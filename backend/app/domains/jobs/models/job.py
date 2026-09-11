from typing import Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    out_dir: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default='queued')
    error: Mapped[Optional[str]] = mapped_column(Text)
    blocks_total: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'retrying', 'done', 'failed')", name="check_job_status"),
        Index("ix_job_status", "status", "id"),
        Index("ix_job_chapter", "chapter_id", "id"),
    )

    # Relationships
    chapter: Mapped["Chapter"] = relationship(back_populates="jobs")