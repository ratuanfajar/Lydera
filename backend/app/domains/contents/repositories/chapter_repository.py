from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import contains_eager, selectinload

from app.core.db import AsyncSession
from app.core.exceptions import ForbiddenException
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models import Block, Chapter, Cp, Module, ModuleStatus
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.domains.contents.models.module_progress import ModuleProgress
from app.domains.contents.repositories.interfaces.chapter_interface import (
    ChapterRepositoryInterface,
)
from app.domains.users.models.student import student_classrooms


class ChapterRepository(ChapterRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_current_max_order(self, chapter_id: int) -> int:
        stmt = select(func.max(Block.reading_order)).where(Block.chapter_id == chapter_id)
        result = await self.db.scalar(stmt)
        return result or 0

    async def bulk_insert_blocks(self, blocks: list[Block]) -> None:
        self.db.add_all(blocks)
        await self.db.flush()

    async def get_chapter_by_id(self, chapter_id: int, teacher_id: int) -> Chapter | None:
        stmt = (
            select(Chapter)
            .join(Module, Chapter.module_id == Module.id)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Chapter.id == chapter_id,
                Classroom.teacher_id == teacher_id,
            )
            .options(
                selectinload(Chapter.blocks)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def student_get_blocks_by_chapter_id(self, chapter_id: int, student_id: int) -> Chapter | None:
        has_access = await self.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException(
                detail="Anda tidak memiliki akses ke chapter ini."
            )
        stmt = (
            select(Chapter)
            .join(Chapter.module)
            .outerjoin(Chapter.blocks)
            .options(contains_eager(Chapter.blocks))
            .where(
                Chapter.id == chapter_id,
                Module.status == ModuleStatus.PUBLISH,
            )
            .order_by(Block.reading_order)
        )
        result = await self.db.scalars(stmt)
        return result.unique().first()

    async def student_get_paginated_blocks(
        self, chapter_id: int, student_id: int, limit: int, offset: int
    ) -> tuple[Chapter | None, list[Block], int]:
        has_access = await self.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException(
                detail="Anda tidak memiliki akses ke chapter ini."
            )
        stmt_chapter = (
            select(Chapter)
            .join(Chapter.module)
            .where(
                Chapter.id == chapter_id,
                Module.status == ModuleStatus.PUBLISH,
            )
        )
        chapter = (await self.db.scalars(stmt_chapter)).first()
        if not chapter:
            return None, [], 0

        stmt_count = (
            select(func.count(Block.id))
            .where(Block.chapter_id == chapter_id)
        )
        total_blocks = (await self.db.scalar(stmt_count)) or 0

        stmt_blocks = (
            select(Block)
            .where(Block.chapter_id == chapter_id)
            .order_by(Block.reading_order)
            .limit(limit)
            .offset(offset)
        )
        blocks = list((await self.db.scalars(stmt_blocks)).all())
        return chapter, blocks, total_blocks

    async def verify_chapter_teacher(
        self,
        chapter_id: int,
        teacher_id: int,
    ) -> bool:
        stmt = (
            select(Chapter.id)
            .join(Module, Module.id == Chapter.module_id)
            .join(Classroom, Classroom.id == Module.classroom_id)
            .where(
                Chapter.id == chapter_id,
                Classroom.teacher_id == teacher_id,
            )
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def student_create_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        stmt = (
            insert(ChapterProgress)
            .values(
                student_id=student_id,
                chapter_id=chapter_id,
                is_done=False,
                completed_at=None,
            ).on_conflict_do_nothing(
                index_elements=[
                    ChapterProgress.student_id,
                    ChapterProgress.chapter_id,
                ]
            )
            .returning(ChapterProgress.id)
        )

        result = await self.db.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        return inserted_id is not None

    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int:
        new_chapter = Chapter(
            module_id=module_id,
            source_file=source_file,
            number=number,
            title=title,
            cp_id=cp_id
        )
        self.db.add(new_chapter)
        await self.db.flush()
        return new_chapter.id

    async def student_update_chapter_progress(self, chapter_id: int, student_id: int) -> bool:
        stmt = (
            update(ChapterProgress)
            .where(
                ChapterProgress.student_id == student_id,
                ChapterProgress.chapter_id == chapter_id,
            )
            .values(
                is_done=True,
                completed_at=func.now(),
            )
            .returning(ChapterProgress.id)
        )
        result = await self.db.execute(stmt)
        chapter_progress_id = result.scalar_one_or_none()
        if chapter_progress_id is None:
            return False
        module_stmt = (select(Chapter.module_id).where(Chapter.id == chapter_id))
        module_id = await self.db.scalar(module_stmt)
        if module_id is None:
            return False

        total_chapters_stmt = (
            select(func.count(Chapter.id))
            .where(
                Chapter.module_id == module_id
            )
        )
        total_chapters = await self.db.scalar(
            total_chapters_stmt
        ) or 0
        completed_chapters_stmt = (
            select(func.count(ChapterProgress.id))
            .join(Chapter, Chapter.id == ChapterProgress.chapter_id,)
            .where(
                Chapter.module_id == module_id, ChapterProgress.student_id == student_id, ChapterProgress.is_done.is_(True),
            )
        )
        completed_chapters = await self.db.scalar(completed_chapters_stmt) or 0

        if total_chapters == 0:
            progress_percentage = 0
            is_done = False

        else:
            progress_percentage = round(
                (completed_chapters / total_chapters) * 100
            )
            is_done = completed_chapters >= total_chapters

        module_progress_stmt = (
            insert(ModuleProgress)
            .values(
                student_id=student_id, module_id=module_id, progress_percentage=progress_percentage, is_done=is_done,
            )
            .on_conflict_do_update(
                index_elements=["student_id", "module_id", ], set_={"progress_percentage": progress_percentage, "is_done": is_done, },
            )
        )
        await self.db.execute(module_progress_stmt)

        return True

    async def validate_student_chapter_access(
        self,
        chapter_id: int,
        student_id: int
    ) -> bool:
        """Checks if student is enrolled in the classroom owning this chapter."""
        stmt = select(
            exists()
            .where(Chapter.id == chapter_id)
            .where(Module.id == Chapter.module_id)
            .where(student_classrooms.c.classroom_id == Module.classroom_id)
            .where(student_classrooms.c.student_id == student_id)
            .where(Module.status == ModuleStatus.PUBLISH)
        )
        result = await self.db.scalar(stmt)
        return bool(result)
