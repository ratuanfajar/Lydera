from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.domains.contents.repositories.repository import ContentRepository
from app.domains.contents.depedencies import get_content_repository
from app.domains.quizz.repositories.repository import QuizRepository
from app.domains.quizz.services.quiz_request_service import QuizRequestService
from app.domains.quizz.services.soal_service import SoalService
from app.domains.quizz.services.quiz_taking_service import QuizTakingService
from app.domains.quizz.services.quiz_result_service import QuizResultService


def get_quiz_repository(db: AsyncSession = Depends(get_db)) -> QuizRepository:
    return QuizRepository(db)


def get_quiz_service(
    repo: QuizRepository = Depends(get_quiz_repository),
    content_repo: ContentRepository = Depends(get_content_repository),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> QuizRequestService:
    return QuizRequestService(repo, content_repo, db, redis)


def get_soal_service(
    repo: QuizRepository = Depends(get_quiz_repository),
    db: AsyncSession = Depends(get_db),
) -> SoalService:
    return SoalService(repo, db)


def get_quiz_taking_service(
    repo: QuizRepository = Depends(get_quiz_repository),
    db: AsyncSession = Depends(get_db),
) -> QuizTakingService:
    return QuizTakingService(repo, repo, repo, db)


def get_quiz_result_service(
    repo: QuizRepository = Depends(get_quiz_repository),
    db: AsyncSession = Depends(get_db),
) -> QuizResultService:
    return QuizResultService(repo, repo, repo, db)
