from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, SmallInteger, ForeignKey, Table
from app.domains.users.models.student import student_classrooms

class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    code: Mapped[str] = mapped_column(String(7), nullable=False, unique=True, index=True)

    grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    classroom_type_id: Mapped[int] = mapped_column(
        ForeignKey(
            "classroom_types.id",
        )
    )

    school_id: Mapped[int] = mapped_column(
        ForeignKey(
            "schools.id",
        )
    )

    teacher_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teachers.id",
        ),
        index=True
    )

    classroom_type: Mapped["ClassroomType"] = relationship(
        back_populates="classrooms"
    )

    school: Mapped["School"] = relationship(
        back_populates="classrooms"
    )

    modules: Mapped[list["Module"]] = relationship(
        back_populates="classroom"
    )
    
    teacher: Mapped["Teacher"] = relationship(
        back_populates="classrooms"
    )

    students: Mapped[list["Student"]] = relationship(
        secondary=student_classrooms,
        back_populates="classrooms"
    )


