from typing import List, Optional
from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class SoalLangkah(Base):
    __tablename__ = "soal_langkah"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    soal_id: Mapped[int] = mapped_column(ForeignKey("soal.id", ondelete="CASCADE"), nullable=False, index=True)
    urutan: Mapped[int] = mapped_column(Integer, nullable=False)
    teks: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("soal_id", "urutan", name="uq_soal_langkah_urutan"),
    )

    # Relationships
    soal: Mapped["Soal"] = relationship(back_populates="langkah")