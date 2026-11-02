from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.redis import get_redis_client
from app.domains.evaluaizer.evaluation import AnswerEvaluator
from app.domains.evaluaizer.services import EvaluaizerService
from app.domains.quizzer.depedencies import get_quiz_repository
from app.domains.quizzer.repositories.repository import QuizRepository


def get_evaluaizer_service(repo: QuizRepository = Depends(get_quiz_repository), db: AsyncSession = Depends(get_db)) -> EvaluaizerService:
    return EvaluaizerService(repo, AnswerEvaluator(repo, db, get_redis_client()))
