from app.core.db import Base
from typing import List

from sqlalchemy import (
    String, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Fase(Base):
    __tablename__="fase"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kode: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    __table_args__ = (
        CheckConstraint("kode IN ('E', 'F')", name="check_fase_kode"),
    )

    cps: Mapped[List["Cp"]] = relationship(back_populates="fase", cascade="all, delete-orphan")
    modules: Mapped[List["Module"]] = relationship(back_populates="fase")