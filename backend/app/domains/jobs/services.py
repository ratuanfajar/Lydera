from app.domains.jobs.repositories.interface import JobRepositoryInterface
from app.core.db import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.jobs.models import Job

class JobService:
    def __init__(self, repo: JobRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    # -- Read (Tanpa Commit) --
    async def get_latest_job_for_chapter(self, chapter_id: int) -> Job | None:
        return await self.repo.get_latest_job_for_chapter(chapter_id)

    # -- Write (Dengan Commit) --
    async def enqueue_job(self, chapter_id: int, pdf_path: str, out_dir: str) -> int:
        try:
            job_id = await self.repo.create_job(chapter_id, pdf_path, out_dir)
            await self.db.commit()
            return job_id
        except Exception as e:
            await self.db.rollback()
            raise e