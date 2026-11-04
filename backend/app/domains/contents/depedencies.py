from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.contents.repositories.block_repository import BlockRepository
from app.domains.contents.repositories.chapter_repository import ChapterRepository
from app.domains.contents.repositories.curriculum_repository import CurriculumRepository
from app.domains.contents.repositories.module_repository import ModuleRepository
from app.domains.contents.repositories.note_repository import NoteRepository
from app.domains.contents.services.block_service import BlockService
from app.domains.contents.services.chapter_service import ChapterService
from app.domains.contents.services.curriculum_service import CurriculumService
from app.domains.contents.services.module_service import ModuleService
from app.domains.contents.services.note_service import RecordNoteService
from app.domains.jobs.depedencies import get_job_repository
from app.domains.jobs.repositories.repository import JobRepository


def get_module_repository(
    db: AsyncSession = Depends(get_db),
) -> ModuleRepository:
    return ModuleRepository(db)


def get_chapter_repository(
    db: AsyncSession = Depends(get_db),
) -> ChapterRepository:
    return ChapterRepository(db)


def get_block_repository(
    db: AsyncSession = Depends(get_db),
) -> BlockRepository:
    return BlockRepository(db)


def get_curriculum_repository(
    db: AsyncSession = Depends(get_db),
) -> CurriculumRepository:
    return CurriculumRepository(db)


def get_note_repository(
    db: AsyncSession = Depends(get_db),
) -> NoteRepository:
    return NoteRepository(db)


def get_block_service(
    repo: BlockRepository = Depends(get_block_repository),
    db: AsyncSession = Depends(get_db),
) -> BlockService:
    return BlockService(repo, db)


def get_curriculum_service(
    repo: CurriculumRepository = Depends(get_curriculum_repository),
) -> CurriculumService:
    return CurriculumService(repo)


def get_note_service(
    repo: NoteRepository = Depends(get_note_repository),
    db: AsyncSession = Depends(get_db),
) -> RecordNoteService:
    return RecordNoteService(repo, db)


def get_module_service(
    repo: ModuleRepository = Depends(get_module_repository),
    job_repo: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
) -> ModuleService:
    return ModuleService(repo, job_repo, db)


def get_chapter_service(
    repo: ChapterRepository = Depends(get_chapter_repository),
    module_repo: ModuleRepository = Depends(get_module_repository),
    db: AsyncSession = Depends(get_db),
) -> ChapterService:
    return ChapterService(repo, module_repo, db)
