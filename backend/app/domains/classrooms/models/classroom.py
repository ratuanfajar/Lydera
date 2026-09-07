from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, SmallInteger, ForeignKey

class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    code: Mapped[str] = mapped_column(String(7), nullable=False)

    grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    classroom_type_id: Mapped[int] = mapped_column(
        ForeignKey(
            "classroom_types.id",
        )
    )

    teacher_id: Mapped[int] = mapped_column(
        ForeignKey(
            "teachers.id",
        )
    )

    classroom_type: Mapped["ClassroomType"] = relationship(
        back_populates="classrooms"
    )
    
    teacher: Mapped["Teacher"] = relationship(
        back_populates="classrooms"
    )


