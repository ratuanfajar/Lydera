from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.quizz.repositories.repository import QuizRepository
from app.domains.quizz.services import QuizService


def get_quiz_repository(db: AsyncSession = Depends(get_db)) -> QuizRepository:
    return QuizRepository(db)


def get_quiz_service(repo: QuizRepository = Depends(get_quiz_repository), db: AsyncSession = Depends(get_db)) -> QuizService:
    return QuizService(repo, db)
