from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, ForeignKey, String, SmallInteger, Table

student_classrooms = Table(
    "student_classrooms",
    Base.metadata,
    Column("student_id", ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("classroom_id", ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True),
)


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

    classrooms: Mapped[list["Classroom"]] = relationship(
        secondary=student_classrooms,
        back_populates="students"
    )

    chapters_progress: Mapped[list["ChapterProgress"]] = relationship(back_populates="student")

    module_progress: Mapped["ModuleProgress"] = relationship(
        back_populates="student"
    )


