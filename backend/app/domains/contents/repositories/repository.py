from datetime import datetime, timezone

from sqlalchemy import exists, func, or_, select, update
from typing import Sequence
from sqlalchemy.dialects.postgresql import insert
from app.tasks.progress_tasks import enqueue_chapter_progress_reset_job, enqueue_module_progress_job
from sqlalchemy.orm import contains_eager, selectinload
from app.domains.contents.models import Block, Module, Chapter, Fase, Cp, ModuleStatus
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.core.db import AsyncSession
from app.domains.contents.models.module_progress import ModuleProgress
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.core.exceptions import ForbiddenException
from app.domains.classrooms.models.classroom import Classroom
from app.domains.users.models.student import student_classrooms
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleStatus
from app.domains.contents.schemas.blocks.regenerate_response import RegenerateResponse

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

    async def get_teacher_blocks(self, block_ids: list[int], teacher_id: int) -> list[Block]:
        unique_ids = list(set(block_ids))
        stmt = (
            select(Block)
            .join(Chapter, Block.chapter_id == Chapter.id)
            .join(Module, Chapter.module_id == Module.id)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Block.id.in_(unique_ids),
                Classroom.teacher_id == teacher_id
            )
        )
        blocks = (await self.db.scalars(stmt)).all()
        
        if len(blocks) != len(unique_ids):
            raise ForbiddenException("Tidak punya akses, beberapa block bukan punya mu.")
        return blocks
    
    async def bulk_update_readable_text(self, update_data: list[dict]) -> bool:
        await self.db.execute(update(Block), update_data)
        await self.db.commit()
        return True
    
    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.db.get(Block, block_id)

    # Fase
    async def get_all_fases(self) -> Sequence[Fase]:
        stmt = select(Fase).order_by(Fase.kode)
        result = await self.db.scalars(stmt)
        return result.all()

    # Module
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

    async def get_detail_module_student(self, module_id:int, classroom_id: int, student_id: int) -> Module | None: 
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

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)
    
    async def get_all_modules_teachers(self, classroom_id:int, teacher_id:int, status: TeacherModuleStatus, search: str | None) -> Sequence[Module]: 
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

    async def get_detail_module_teacher(self, module_id:int, classroom_id: int, teacher_id: int) -> Module | None: 
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
    
    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)

    async def create_module_teacher(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id:int, fase_id: int | None) -> Module | None:
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

    async def publish_module(self, module_id:int, teacher_id:int) -> True: 
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
        module.status = ModuleStatus.PUBLISH
        await self.db.commit()

        return True

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

    # Cps
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]:
        stmt = select(Cp).where(Cp.fase_id == fase_id).order_by(Cp.domain)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_cp_by_id(self, cp_id: int) -> Cp | None:
        return await self.db.get(Cp, cp_id)

    # Chapter
    async def student_upsert_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        completed_at = datetime.now(timezone.utc)
        stmt = (
            insert(ChapterProgress)
            .values(
                student_id=student_id,
                chapter_id=chapter_id,
                is_done=True,
                completed_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update( index_elements=["student_id", "chapter_id"], set_={ "is_done": True, "completed_at": completed_at, }, )
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
        chapter_progress_id = result.scalar_one_or_none()
        if chapter_progress_id is None: 
            return False
        module_stmt = ( select(Chapter.module_id) .where(Chapter.id == chapter_id) )
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
            .join( Chapter, Chapter.id == ChapterProgress.chapter_id, ) 
            .where( 
                Chapter.module_id == module_id, ChapterProgress.student_id == student_id, ChapterProgress.is_done.is_(True), 
            ) 
        ) 
        completed_chapters = await self.db.scalar( completed_chapters_stmt ) or 0 
    
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
                    index_elements=[ "student_id", "module_id", ], set_={ "progress_percentage": progress_percentage, "is_done": is_done, }, 
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
