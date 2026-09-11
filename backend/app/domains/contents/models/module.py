from datetime import datetime
from typing import List, Optional
from app.core.db import Base
from enum import Enum
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    String, Integer, Text, CHAR, ForeignKey, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class ModuleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    fase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fase.id"))
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"),index=True)
    status: Mapped[ModuleStatus] = mapped_column(
        SQLEnum(ModuleStatus, native_enum=False, length=20),
        nullable=False,
        default=ModuleStatus.DRAFT,
    )

    __table_args__ = (
        Index(
            "ix_modules_classroom_status_updated",
            "classroom_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_modules_classroom_status",
            "classroom_id",
            "status"
        ),
        Index(
            "idx_modules_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )
    

    # Relationships
    classroom: Mapped["Classroom"] = relationship(back_populates="modules")
    fase: Mapped[Optional["Fase"]] = relationship(back_populates="modules")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="module", cascade="all, delete-orphan")
    quiz_requests: Mapped[List["QuizRequest"]] = relationship(back_populates="module", cascade="all, delete-orphan")
    module_progress: Mapped[Optional["ModuleProgress"]] = relationship(
        back_populates="module",
        uselist=False 
    )
