from typing import Sequence

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import contains_eager, selectinload

from app.core.db import AsyncSession
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models import Chapter, Module, ModuleStatus
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.domains.contents.models.module_progress import ModuleProgress
from app.domains.contents.repositories.interfaces.module_interface import (
    ModuleRepositoryInterface,
)
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleStatus


class ModuleRepository(ModuleRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)

    async def get_all_modules_student(
        self,
        classroom_id: int,
        student_id: int,
        status: StudentModuleStatus = StudentModuleStatus.NOT_DONE,
    ) -> Sequence[Module]:
        stmt = (
            select(Module)
            .outerjoin(
                ModuleProgress,
                (ModuleProgress.module_id == Module.id)
                & (ModuleProgress.student_id == student_id),
            )
            .options(
                contains_eager(Module.module_progress),
            )
            .where(
                Module.classroom_id == classroom_id,
                Module.status == ModuleStatus.PUBLISH,
            )
            .order_by(Module.updated_at)
        )

        match status:
            case StudentModuleStatus.DONE:
                stmt = stmt.where(
                    ModuleProgress.is_done.is_(True)
                )

            case StudentModuleStatus.NOT_DONE:
                stmt = stmt.where(
                    or_(
                        ModuleProgress.id.is_(None),
                        ModuleProgress.is_done.is_(False),
                    )
                )

            case StudentModuleStatus.ALL:
                pass

        result = await self.db.scalars(stmt)

        return result.unique().all()

    async def get_detail_module_student(self, module_id: int, classroom_id: int, student_id: int) -> Module | None:
        stmt = (
            select(Module)
            .options(
                selectinload(Module.module_progress)
            )
            .outerjoin(Module.chapters)
            .outerjoin(
                ChapterProgress,
                (ChapterProgress.chapter_id == Chapter.id) & (ChapterProgress.student_id == student_id),
            )
            .options(
                contains_eager(Module.chapters).contains_eager(Chapter.chapter_progress)
            )
            .where(
                Module.id == module_id,
                Module.classroom_id == classroom_id,
                Module.status == ModuleStatus.PUBLISH,
            )
            .order_by(Chapter.number)
        )

        result = await self.db.scalars(stmt)
        module = result.unique().first()
        return module

    async def get_all_modules_teachers(self, classroom_id: int, teacher_id: int, status: TeacherModuleStatus, search: str | None) -> Sequence[Module]:
        stmt = (
            select(Module)
            .join(Classroom, Classroom.id == Module.classroom_id)
            .where(
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,
            )
        )

        if status != TeacherModuleStatus.ALL:
            stmt = stmt.where(Module.status == status)

        if search:
            stmt = stmt.where(Module.title.ilike(f"%{search.strip()}%"))

        stmt = stmt.order_by(Module.id)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_detail_module_teacher(self, module_id: int, classroom_id: int, teacher_id: int) -> Module | None:
        stmt = (
            select(Module)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .outerjoin(Module.chapters)
            .options(
                contains_eager(Module.chapters)
            )
            .where(
                Module.id == module_id,
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,
            )
            .order_by(Chapter.number)
        )

        result = await self.db.scalars(stmt)
        module = result.unique().first()
        return module

    async def delete_module_teacher(self, module_id: int, classroom_id: int, teacher_id: int) -> bool:
        classroom_subquery = (
            select(Classroom.id)
            .where(
                Classroom.id == classroom_id,
                Classroom.teacher_id == teacher_id
            )
        )

        stmt = (
            delete(Module)
            .where(
                Module.id == module_id,
                Module.classroom_id.in_(classroom_subquery)
            )
        )

        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def create_module_teacher(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id: int, fase_id: int | None) -> Module | None:
        is_owner = await self.db.scalar(
            select(
                exists().where(
                    Classroom.id == classroom_id,
                    Classroom.teacher_id == teacher_id,
                )
            )
        )
        if not is_owner:
            return None
        new_module = Module(title=title, description=description, status=status.value, classroom_id=classroom_id, fase_id=fase_id)
        self.db.add(new_module)
        await self.db.flush()
        return new_module

    async def set_module_status(self, module_id: int, teacher_id: int, status: ModuleStatus) -> bool: 
        ownership_stmt = (
            select(Module)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Module.id == module_id,
                Classroom.teacher_id == teacher_id
            )
        )
        result = await self.db.execute(ownership_stmt)
        module = result.scalar_one_or_none()
        if not module:
            return False
        module.status = status
        await self.db.commit()

        return True