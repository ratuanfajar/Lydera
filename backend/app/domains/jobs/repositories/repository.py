from ast import Module

from app.domains.jobs.repositories.interface import JobRepositoryInterface
from app.core.db import AsyncSession
from sqlalchemy import select
from app.domains.jobs.models import Job
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models.chapter import Chapter

class JobRepository(JobRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_next_queued_job(self) -> Job | None:
        stmt = select(Job).where(Job.status == 'queued').order_by(Job.id.asc()).limit(1)
        return await self.db.scalar(stmt)

    async def update_job_status(self, job: Job, status: str, error: str = None, blocks_total: int = None) -> None:
        job.status = status
        if error:
            job.error = error
        if blocks_total is not None:
            job.blocks_total = blocks_total

    async def get_latest_job_for_chapter(self, chapter_id: int) -> Job | None:
        stmt = select(Job).where(Job.chapter_id == chapter_id).order_by(Job.id.desc()).limit(1)
        return await self.db.scalar(stmt)

    async def create_job(self, chapter_id: int, pdf_path: str, out_dir: str) -> int:
        new_job = Job(
            chapter_id=chapter_id,
            pdf_path=pdf_path,
            out_dir=out_dir,
            status='queued'
        )
        self.db.add(new_job)
        await self.db.flush()
        return new_job.id

    async def get_job_file_paths_by_module(self, module_id: int, classroom_id: int, teacher_id: int) -> list[tuple[str | None, str | None]]:
        """Fetches pdf_path and out_dir for all jobs linked to chapters in the module."""
        stmt = (
            select(Job.pdf_path, Job.out_dir)
            .join(Chapter, Job.chapter_id == Chapter.id)
            .join(Module, Chapter.module_id == Module.id)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Module.id == module_id,
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.all())