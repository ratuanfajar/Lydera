from typing import List, Optional
from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class SoalOpsi(Base):
    __tablename__ = "soal_opsi"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    soal_id: Mapped[int] = mapped_column(ForeignKey("soal.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    opsi_text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("label IN ('A', 'B', 'C', 'D')", name="check_opsi_label"),
        UniqueConstraint("soal_id", "label", name="uq_soal_opsi_label"),
    )

    # Relationships
    soal: Mapped["Soal"] = relationship(back_populates="opsi")