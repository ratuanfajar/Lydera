from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from app.core.db import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),unique=True, nullable=False)

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)

    user: Mapped["User"] = relationship(
        back_populates="teacher"
    )

    classrooms: Mapped[list["Classroom"]] = relationship(
        back_populates="teacher"
    )

    school: Mapped["School"] = relationship(
        back_populates="teachers"
    )