from core.db import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String


class Student(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    nis: Mapped[str] = mapped_column(String(255), nullable=False)

    nisn: Mapped[str] = mapped_column(String(255), nullable=False)

    grade: Mapped[str] = mapped_column(String(255), nullable=False)


