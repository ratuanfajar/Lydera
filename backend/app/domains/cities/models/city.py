from core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    schools: Mapped[list["School"]] = relationship(
        back_populates="city"
    )
