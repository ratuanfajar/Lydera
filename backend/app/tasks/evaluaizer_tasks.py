from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.taskiq import broker
from app.domains.evaluaizer.evaluation import AnswerEvaluator
from app.domains.quizzer.repositories.quiz_progress_repository import QuizProgressRepository
from app.domains.quizzer.repositories.soal_repository import SoalRepository


@broker.task
async def evaluate_quiz_answers_task(quiz_request_id: int, student_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await AnswerEvaluator(SoalRepository(db), QuizProgressRepository(db), db, get_redis_client()).evaluate(quiz_request_id, student_id)
