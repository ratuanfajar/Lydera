from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base


class SoalJawabanLangkah(Base):
    __tablename__ = "soal_jawaban_langkah"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jawaban_id: Mapped[int] = mapped_column(ForeignKey("soal_jawaban.id", ondelete="CASCADE"), nullable=False)
    urutan: Mapped[int] = mapped_column(Integer, nullable=False)
    teks: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("jawaban_id", "urutan", name="uq_soal_jawaban_langkah_urutan"),
    )

    # Relationships
    jawaban: Mapped["SoalJawaban"] = relationship(back_populates="langkah")
