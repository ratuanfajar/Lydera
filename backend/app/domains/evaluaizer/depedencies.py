from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.domains.evaluaizer.evaluation import AnswerEvaluator
from app.domains.evaluaizer.services import EvaluaizerService
from app.domains.quizzer.depedencies import get_soal_repository, get_quiz_progress_repository
from app.domains.quizzer.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface
from app.domains.quizzer.repositories.interfaces.soal_interface import SoalRepositoryInterface

def get_evaluaizer_service(soal_repo: SoalRepositoryInterface = Depends(get_soal_repository), quiz_progress_repo: QuizProgressRepositoryInterface = Depends(get_quiz_progress_repository), db: AsyncSession = Depends(get_db)) -> EvaluaizerService:
    return EvaluaizerService(repo, AnswerEvaluator(repo, db, get_redis_client()))
