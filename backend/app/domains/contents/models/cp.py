from app.core.db import Base
from typing import List

from sqlalchemy import (
    String, Text, ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Cp(Base):
    __tablename__ = "cp"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fase_id: Mapped[int] = mapped_column(ForeignKey("fase.id"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    cp_text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "domain IN ('Bilangan', 'Aljabar dan Fungsi', 'Pengukuran', 'Geometri', 'Analisis Data dan Peluang', 'Fungsi', 'Kalkulus')",
            name="check_cp_domain"
        ),
        UniqueConstraint("fase_id", "domain", name="uq_cp_fase_domain"),
    )

    fase: Mapped["Fase"] = relationship(back_populates="cps")
    chapters: Mapped[List["Chapter"]] = relationship(back_populates="cp")