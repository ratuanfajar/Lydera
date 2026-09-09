from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.domains.contents.repositories.repository import ContentRepository
from app.domains.contents.services import ContentService

def get_content_repository(db: AsyncSession = Depends(get_db)) -> ContentRepository:
    return ContentRepository(db)

def get_content_service(repo: ContentRepository = Depends(get_content_repository), db: AsyncSession = Depends(get_db)) -> ContentService:
    return ContentService(repo,db)
