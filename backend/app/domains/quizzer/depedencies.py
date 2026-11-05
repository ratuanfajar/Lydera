from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.domains.contents.depedencies import get_module_repository
from app.domains.contents.repositories.module_repository import ModuleRepository
from app.domains.quizzer.repositories.quiz_progress_repository import QuizProgressRepository
from app.domains.quizzer.repositories.quiz_request_repository import QuizRequestRepository
from app.domains.quizzer.repositories.soal_repository import SoalRepository
from app.domains.quizzer.services.quiz_request_service import QuizRequestService
from app.domains.quizzer.services.soal_service import SoalService
from app.domains.quizzer.services.quiz_taking_service import QuizTakingService


def get_quiz_request_repository(
    db: AsyncSession = Depends(get_db),
) -> QuizRequestRepository:
    return QuizRequestRepository(db)


def get_soal_repository(
    db: AsyncSession = Depends(get_db),
) -> SoalRepository:
    return SoalRepository(db)


def get_quiz_progress_repository(
    db: AsyncSession = Depends(get_db),
) -> QuizProgressRepository:
    return QuizProgressRepository(db)


def get_quiz_service(
    repo: QuizRequestRepository = Depends(get_quiz_request_repository),
    module_repo: ModuleRepository = Depends(get_module_repository),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> QuizRequestService:
    return QuizRequestService(repo, module_repo, db, redis)


def get_soal_service(
    quiz_repo: QuizRequestRepository = Depends(get_quiz_request_repository),
    repo: SoalRepository = Depends(get_soal_repository),
    db: AsyncSession = Depends(get_db),
) -> SoalService:
    return SoalService(quiz_repo, repo, db)


def get_quiz_taking_service(
    progress_repo: QuizProgressRepository = Depends(get_quiz_progress_repository),
    soal_repo: SoalRepository = Depends(get_soal_repository),
    quiz_repo: QuizRequestRepository = Depends(get_quiz_request_repository),
    db: AsyncSession = Depends(get_db),
) -> QuizTakingService:
    return QuizTakingService(progress_repo, soal_repo, quiz_repo, db)
