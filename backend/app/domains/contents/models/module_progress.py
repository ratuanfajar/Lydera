from sqlalchemy import Boolean, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

class ModuleProgress(Base):
    __tablename__ = "modules_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("student_id", "module_id", name="uq_student_module_progress"),
    )
    

    module: Mapped["Module"] = relationship(
        back_populates="module_progress"
    )

    student: Mapped["Student"] = relationship(
            back_populates="module_progress"
    )
