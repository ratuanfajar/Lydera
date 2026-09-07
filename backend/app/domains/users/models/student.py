from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, SmallInteger


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),unique=True, nullable=False, index=True)
    
    nis: Mapped[str] = mapped_column(String(255), nullable=True)

    nisn: Mapped[str] = mapped_column(String(255), nullable=True)

    grade: Mapped[int] = mapped_column(SmallInteger, nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="student"
    )


