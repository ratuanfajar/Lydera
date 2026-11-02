from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.quizzer.repositories.repository import QuizRepository
from app.domains.quizzer.services import QuizService
from app.core.redis import get_redis_client


def get_quiz_repository(db: AsyncSession = Depends(get_db)) -> QuizRepository:
    return QuizRepository(db)


def get_quiz_service(repo: QuizRepository = Depends(get_quiz_repository), db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis_client)) -> QuizService:
    return QuizService(repo, db, redis)
