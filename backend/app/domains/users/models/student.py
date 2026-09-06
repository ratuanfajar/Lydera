from core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, SmallInteger


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),unique=True, nullable=False, index=True)
    
    nis: Mapped[str] = mapped_column(String(255))

    nisn: Mapped[str] = mapped_column(String(255))

    grade: Mapped[int] = mapped_column(SmallInteger)

    user: Mapped["User"] = relationship(
        back_populates="student"
    )


