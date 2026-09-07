from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey

class School(Base):
    __tablename__="schools"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    city_id: Mapped[int] = mapped_column(
        ForeignKey(
            "cities.id",
            ondelete="CASCADE"
            ),
        index=True,
        nullable=False
    )
    
    city: Mapped["City"] = relationship(
        back_populates="schools"
    )

    classrooms: Mapped[list["Classroom"]] = relationship(
        back_populates="school"
    )

    teachers: Mapped[list["Teacher"]] = relationship(
        back_populates="school"
    )