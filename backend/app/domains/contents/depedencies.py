from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.contents.repositories.repository import ContentRepository
from app.domains.contents.services.block_service import BlockService
from app.domains.contents.services.chapter_service import ChapterService
from app.domains.contents.services.curriculum_service import CurriculumService
from app.domains.contents.services.module_service import ModuleService
from app.domains.contents.services.note_service import RecordNoteService
from app.domains.jobs.depedencies import get_job_repository
from app.domains.jobs.repositories.repository import JobRepository


def get_content_repository(
    db: AsyncSession = Depends(get_db),
) -> ContentRepository:
    return ContentRepository(db)


def get_block_service(
    repo: ContentRepository = Depends(get_content_repository),
    db: AsyncSession = Depends(get_db),
) -> BlockService:
    return BlockService(repo, db)


def get_curriculum_service(
    repo: ContentRepository = Depends(get_content_repository),
) -> CurriculumService:
    return CurriculumService(repo)


def get_note_service(
    repo: ContentRepository = Depends(get_content_repository),
    db: AsyncSession = Depends(get_db),
) -> RecordNoteService:
    return RecordNoteService(repo, db)


def get_module_service(
    repo: ContentRepository = Depends(get_content_repository),
    job_repo: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
) -> ModuleService:
    return ModuleService(repo, job_repo, db)


def get_chapter_service(
    repo: ContentRepository = Depends(get_content_repository),
    db: AsyncSession = Depends(get_db),
) -> ChapterService:
    return ChapterService(repo, repo, db)
