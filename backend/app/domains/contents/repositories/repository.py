# from datetime import datetime, timezone

# from sqlalchemy import delete, exists, func, or_, select, update
# from typing import Sequence
# from sqlalchemy.dialects.postgresql import insert
# from app.tasks.progress_tasks import enqueue_chapter_progress_reset_job, enqueue_module_progress_job
# from sqlalchemy.orm import contains_eager, selectinload
# from app.domains.contents.models import Block, Module, Chapter, Fase, Cp, ModuleStatus
# from app.domains.contents.repositories.interface import ContentRepositoryInterface
# from app.core.db import AsyncSession
# from app.domains.contents.models.module_progress import ModuleProgress
# from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
# from app.domains.contents.models.chapter_progress import ChapterProgress
# from app.core.exceptions import ForbiddenException
# from app.domains.classrooms.models.classroom import Classroom
# from app.domains.users.models.student import student_classrooms
# from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleStatus
# from app.domains.contents.schemas.blocks.regenerate_response import RegenerateResponse

# class ContentRepository(ContentRepositoryInterface):
#     def __init__(self, db: AsyncSession):
#         self.db = db

#     # # Chapter
#     # async def student_upsert_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
#     #     completed_at = datetime.now(timezone.utc)
#     #     stmt = (
#     #         insert(ChapterProgress)
#     #         .values(
#     #             student_id=student_id,
#     #             chapter_id=chapter_id,
#     #             is_done=True,
#     #             completed_at=datetime.now(timezone.utc),
#     #         )
#     #         .on_conflict_do_update( index_elements=["student_id", "chapter_id"], set_={ "is_done": True, "completed_at": completed_at, }, )
#     #         .returning(ChapterProgress.id) 
#     #     )
    
#     #     result = await self.db.execute(stmt)
#     #     inserted_id = result.scalar_one_or_none()
#     #     return inserted_id is not None
            