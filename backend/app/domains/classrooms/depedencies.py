from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.domains.classrooms.repositories.repository import ClassroomRepository, ClassroomTypeRepository
from app.domains.classrooms.services import ClassroomService, ClassroomTypeService

def get_classroom_repository(db: AsyncSession = Depends(get_db)) -> ClassroomRepository:
    return ClassroomRepository(db)

def get_classroom_type_repository(db: AsyncSession = Depends(get_db)) -> ClassroomTypeRepository:
    return ClassroomTypeRepository(db)

def get_classroom_service(repo: ClassroomRepository = Depends(get_classroom_repository), db: AsyncSession = Depends(get_db)) -> ClassroomService:
    return ClassroomService(repo,db)

def get_classroom_type_service(repo: ClassroomTypeRepository = Depends(get_classroom_type_repository), db: AsyncSession = Depends(get_db)) -> ClassroomTypeService:
    return ClassroomTypeService(repo,db)