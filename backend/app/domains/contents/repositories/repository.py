from sqlalchemy import exists, func, insert, or_, select, update
from typing import Sequence

from sqlalchemy.orm import contains_eager
from app.domains.contents.models import Block, Module, Chapter, Fase, Cp, ModuleStatus
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.core.db import AsyncSession
from app.domains.contents.models.module_progress import ModuleProgress
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.core.exceptions import ForbiddenException
from app.domains.classrooms.models.classroom import Classroom
from app.domains.users.models.student import student_classrooms
class ContentRepository(ContentRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    # Block
    async def get_current_max_order(self, chapter_id: int) -> int:
        stmt = select(func.max(Block.reading_order)).where(Block.chapter_id == chapter_id)
        result = await self.db.scalar(stmt)
        return result or 0

    async def bulk_insert_blocks(self, blocks: list[Block]) -> None:
        self.db.add_all(blocks)
        await self.db.flush()

    async def student_get_blocks_by_chapter_id(self, chapter_id: int, student_id:int) -> Chapter | None:
        has_access = await self.repo.validate_student_chapter_access(chapter_id, student_id)
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

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.db.get(Block, block_id)

    # Fase
    async def get_all_fases(self) -> Sequence[Fase]:
        stmt = select(Fase).order_by(Fase.kode)
        result = await self.db.scalars(stmt)
        return result.all()

    # Module
    async def get_all_modules_student(self, classroom_id: int, student_id: int, status:StudentModuleStatus = StudentModuleStatus.NOT_DONE) -> Sequence[Module]:
        stmt = (
            select(Module)
            .outerjoin(
                ModuleProgress,
                (ModuleProgress.module_id == Module.id) & (ModuleProgress.student_id == student_id),
            )
            .options(contains_eager(Module.module_progress))
            .where(
                Module.classroom_id == classroom_id,
                Module.status == ModuleStatus.PUBLISH
            )
            .order_by(Module.updated_at)
        )

        match status:
            case StudentModuleStatus.DONE:
                stmt = stmt.where(ModuleProgress.is_done.is_(True))
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

    async def get_detail_module_student(self, module_id:int, classroom_id: int, student_id: int) -> Module | None: 
        stmt = (
            select(Module)
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

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)
    
    async def get_all_modules(self) -> Sequence[Module]:
        stmt = select(Module).order_by(Module.id)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)

    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, fase_id: int | None) -> Module:
        new_module = Module(title=title, description=description, status=status.name, classroom_id=classroom_id, fase_id=fase_id)
        self.db.add(new_module)
        await self.db.flush()
        return new_module

    # Cps
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]:
        stmt = select(Cp).where(Cp.fase_id == fase_id).order_by(Cp.domain)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_cp_by_id(self, cp_id: int) -> Cp | None:
        return await self.db.get(Cp, cp_id)

    # Chapter
    async def student_upsert_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        stmt = (
            insert(ChapterProgress)
            .values(
                student_id=student_id,
                chapter_id=chapter_id,
                is_done=False
            )
            .on_conflict_do_nothing(
                index_elements=["student_id", "chapter_id"]
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

    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None:
        return await self.db.get(Chapter, chapter_id)

    async def student_update_chapter_progress(self, chapter_id: int, student_id:int) -> bool:
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
        updated_id = result.scalar_one_or_none()
        
        return updated_id is not None
        
    
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
