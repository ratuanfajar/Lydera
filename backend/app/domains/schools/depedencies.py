from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from domains.schools.repositories.repository import SchoolRepository
from domains.schools.services import SchoolService

def get_school_repository(db: AsyncSession = Depends(get_db)) -> SchoolRepository:
    return SchoolRepository(db)

def get_school_service(repo: SchoolRepository = Depends(get_school_repository), db: AsyncSession = Depends(get_db)) -> SchoolService:
    return SchoolService(repo,db)