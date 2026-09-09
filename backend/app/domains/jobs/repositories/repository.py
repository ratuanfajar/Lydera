from app.domains.jobs.repositories.interface import JobRepositoryInterface
from app.core.db import AsyncSession
from sqlalchemy import select
from app.domains.jobs.models import Job

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