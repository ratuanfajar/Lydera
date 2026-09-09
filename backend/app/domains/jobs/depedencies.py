from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.domains.jobs.repositories.repository import JobRepository
from app.domains.jobs.services import JobService

def get_job_repository(db: AsyncSession = Depends(get_db)) -> JobRepository:
    return JobRepository(db)

def get_job_service(repo: JobRepository = Depends(get_job_repository), db: AsyncSession = Depends(get_db)) -> JobService:
    return JobService(repo,db)
