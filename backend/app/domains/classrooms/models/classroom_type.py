from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

class ClassroomType(Base):
    __tablename__ = "classroom_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    classrooms: Mapped[list["Classroom"]] = relationship(
        back_populates="classroom_type"
    )

