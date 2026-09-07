from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from domains.users.repositories.repository import UserRepository, TeacherRepository, StudentRepository
from domains.users.services import UserService, TeacherService, StudentService

def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)

def get_user_service(repo: UserRepository = Depends(get_user_repository), db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(repo,db)

def get_teacher_repository(db: AsyncSession = Depends(get_db)) -> TeacherRepository:
    return TeacherRepository(db)

def get_teacher_service(
    repo: TeacherRepository = Depends(get_teacher_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db),
) -> TeacherService:
    return TeacherService(user_repo, repo, db)

def get_student_repository(db: AsyncSession = Depends(get_db)) -> StudentRepository:
    return StudentRepository(db)

def get_student_service(
    repo: StudentRepository = Depends(get_student_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db),
) -> StudentService:
    return StudentService(user_repo, repo, db)