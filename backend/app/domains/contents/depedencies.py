from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.domains.contents.repositories.repository import ContentRepository
from app.domains.contents.services import ContentService
from app.domains.jobs.depedencies import get_job_repository
from app.domains.jobs.repositories.repository import JobRepository

def get_content_repository(db: AsyncSession = Depends(get_db)) -> ContentRepository:
    return ContentRepository(db)

def get_content_service(repo: ContentRepository = Depends(get_content_repository), job_repo: JobRepository = Depends(get_job_repository), db: AsyncSession = Depends(get_db)) -> ContentService:
    return ContentService(repo,job_repo,db)
