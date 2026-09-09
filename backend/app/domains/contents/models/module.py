from datetime import datetime
from typing import List, Optional
from app.core.db import Base
from sqlalchemy import (
    String, Integer, Text, CHAR, ForeignKey, CheckConstraint, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    fase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fase.id"))

    # Relationships
    fase: Mapped[Optional["Fase"]] = relationship(back_populates="modules")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="module", cascade="all, delete-orphan")
    quiz_requests: Mapped[List["QuizRequest"]] = relationship(back_populates="module", cascade="all, delete-orphan")
