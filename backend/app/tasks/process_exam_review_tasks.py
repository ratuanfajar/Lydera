from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domains.quizz.models import QuizProgress, QuizReviewStatus
from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.quizz.models.quiz_progress import QuizReviewStatus
from app.domains.quizz.models.quiz_request import QuizRequest
from app.domains.quizz.models.soal_jawaban import SoalJawaban

@broker.task
async def process_exam_review_task(quiz_id: int, student_id: int) -> None:
    """Calculates student score by comparing selected_option with correct_option."""
    async with AsyncSessionLocal() as db:
        # 1. Fetch progress record
        stmt = select(QuizProgress).where(
            QuizProgress.quiz_request_id == quiz_id,
            QuizProgress.student_id == student_id,
        )
        progress = (await db.scalars(stmt)).one_or_none()
        if not progress:
            return

        try:
            # Mark processing
            progress.review_status = QuizReviewStatus.PROCESSING
            await db.commit()

            stmt_quiz = (
                select(QuizRequest)
                .where(QuizRequest.id == quiz_id)
                .options(selectinload(QuizRequest.soals))
            )

            quiz = (await db.scalars(stmt_quiz)).one_or_none()
            if not quiz or not quiz.soals:
                progress.score = 0
                progress.is_done = True
                progress.review_status = QuizReviewStatus.COMPLETED
                progress.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            soal_ids = [soal.id for soal in quiz.soals]
            stmt_jawaban = select(SoalJawaban).where(
                SoalJawaban.soal_id.in_(soal_ids),
                SoalJawaban.student_id == student_id,
            )
            jawaban_list = (await db.scalars(stmt_jawaban)).all()
            jawaban_by_soal = {j.soal_id: j for j in jawaban_list}

            correct_count = 0
            total_soal = len(quiz.soals)

            for soal in quiz.soals:
                jawaban = jawaban_by_soal.get(soal.id)
                if jawaban:
                    is_correct = jawaban.selected_option.upper() == soal.correct_option.upper()
                    jawaban.is_correct = is_correct
                    if is_correct:
                        correct_count += 1

            score_percentage = int((correct_count / total_soal) * 100) if total_soal > 0 else 0

            progress.score = score_percentage
            progress.is_done = True
            progress.review_status = QuizReviewStatus.COMPLETED
            progress.completed_at = datetime.now(timezone.utc)
            progress.review_error = None
            await db.commit()

        except Exception as exc:
            await db.rollback()
            progress.review_status = QuizReviewStatus.FAILED
            progress.review_error = str(exc)
            await db.commit()
            raise exc
        