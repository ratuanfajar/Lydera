from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.domains.contents.depedencies import get_module_repository
from app.domains.contents.repositories.module_repository import ModuleRepository
from app.domains.quizz.repositories.quiz_progress_repository import QuizProgressRepository
from app.domains.quizz.repositories.quiz_request_repository import QuizRequestRepository
from app.domains.quizz.repositories.soal_repository import SoalRepository
from app.domains.quizz.services.quiz_request_service import QuizRequestService
from app.domains.quizz.services.soal_service import SoalService
from app.domains.quizz.services.quiz_taking_service import QuizTakingService
from app.domains.quizz.services.quiz_result_service import QuizResultService


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
    repo: SoalRepository = Depends(get_soal_repository),
    db: AsyncSession = Depends(get_db),
) -> SoalService:
    return SoalService(repo, db)


def get_quiz_taking_service(
    progress_repo: QuizProgressRepository = Depends(get_quiz_progress_repository),
    soal_repo: SoalRepository = Depends(get_soal_repository),
    quiz_repo: QuizRequestRepository = Depends(get_quiz_request_repository),
    db: AsyncSession = Depends(get_db),
) -> QuizTakingService:
    return QuizTakingService(progress_repo, soal_repo, quiz_repo, db)


def get_quiz_result_service(
    progress_repo: QuizProgressRepository = Depends(get_quiz_progress_repository),
    soal_repo: SoalRepository = Depends(get_soal_repository),
    quiz_repo: QuizRequestRepository = Depends(get_quiz_request_repository),
    db: AsyncSession = Depends(get_db),
) -> QuizResultService:
    return QuizResultService(progress_repo, soal_repo, quiz_repo, db)
