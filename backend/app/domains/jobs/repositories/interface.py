from abc import ABC, abstractmethod

from app.domains.jobs.models.job import Job

class JobRepositoryInterface(ABC):
    @abstractmethod
    async def get_next_queued_job(self) -> Job | None: pass
    @abstractmethod
    async def update_job_status(self, job: Job, status: str, error: str = None, blocks_total: int = None) -> None: pass
    @abstractmethod
    async def get_latest_job_for_chapter(self, chapter_id: int) -> Job | None: pass
    @abstractmethod
    async def create_job(self, chapter_id: int, pdf_path: str, out_dir: str) -> int: pass