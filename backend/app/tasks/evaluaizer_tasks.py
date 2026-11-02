from app.core.db import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.core.taskiq import broker
from app.domains.evaluaizer.evaluation import AnswerEvaluator
from app.domains.quizzer.repositories.repository import QuizRepository


@broker.task
async def evaluate_quiz_answers_task(quiz_request_id: int, student_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await AnswerEvaluator(QuizRepository(db), db, get_redis_client()).evaluate(quiz_request_id, student_id)
