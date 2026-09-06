from core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    password: Mapped[str] = mapped_column(String(255), nullable=False)

    teacher: Mapped["Teacher | None"] = relationship(
        back_populates="user"
    )

    student: Mapped["Student | None"] = relationship(
        back_populates="user"
    )


