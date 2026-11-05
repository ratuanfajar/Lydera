import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizzer.models import SoalJawaban
from app.domains.quizzer.models.quiz_progress import QuizReviewStatus
from app.domains.quizzer.models.quiz_request import QuizRequestStatus
from app.domains.quizzer.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface
from app.domains.quizzer.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizzer.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizzer.schemas import SoalSubmitRequest
from app.domains.quizzer.schemas.quiz_request_student_query import QuizRequestStudentQuery, QuizRequestStudentQueryStatus
from app.domains.quizzer.schemas.quiz_request_student_response import (
    QuestionAnswerStudentResponse, QuestionOptionResponse, QuestionStimulusStudentResponse,
    QuestionStudentSteps, QuizRequestQuestionStudentResponse, QuizRequestStudentResponse,
)
from app.domains.quizzer.schemas.step_request import AddStepRequest
from app.tasks.process_exam_review_tasks import process_exam_review_task

SUBMIT_GRACE = timedelta(seconds=10)

class QuizTakingService:
    def __init__(
        self,
        progress_repo: QuizProgressRepositoryInterface,
        soal_repo: SoalRepositoryInterface,
        quiz_repo: QuizRequestRepositoryInterface,
        db: AsyncSession,
    ):
        self.progress_repo = progress_repo
        self.soal_repo = soal_repo
        self.quiz_repo = quiz_repo
        self.db = db

    async def get_quizzes_student(self, query: QuizRequestStudentQuery, student_id: int) -> list[QuizRequestStudentResponse]:
        await self._ensure_student_in_classroom(student_id, query.classroom_id)
        quizzes = await self.quiz_repo.get_quizzes_student(query.classroom_id, student_id, query.status)
        return [QuizRequestStudentResponse.model_validate(q) for q in quizzes]

    async def initialize_and_stream_quiz(self, student_id: int, quiz_id: int) -> AsyncGenerator[str, None]:
        now = datetime.now(timezone.utc)
        quiz, progress = await self.progress_repo.get_or_create_quiz_progress(student_id, quiz_id)

        if quiz.status_published == QuizRequestStatus.DRAFT:
            raise BadRequestException("Sesi kuis belum di publik")

        if now < quiz.start_time or now > quiz.end_time:
            raise BadRequestException("Sesi kuis tidak sedang aktif.")

        session_active = False
        if progress.started_at is not None and not progress.is_done:
            session_duration = timedelta(minutes=quiz.max_duration_minutes)
            session_deadline = min(progress.started_at + session_duration, quiz.end_time)

            if now < session_deadline:
                session_active = True

        if not session_active:
            if progress.attempt_count >= quiz.max_retry:
                raise BadRequestException("Anda telah mencapai batas maksimal percobaan kuis")

            progress.attempt_count += 1
            progress.completed_at = None
            progress.is_done = False
            progress.started_at = now
            progress.review_status = QuizReviewStatus.PENDING

            await self.progress_repo.db.commit()

        target_end_time = min(
            progress.started_at + timedelta(minutes=quiz.max_duration_minutes),
            quiz.end_time
        )

        soal_list = await self.soal_repo.get_quiz_questions_with_answers(quiz_id, student_id)
        questions_payload = []
        for soal in soal_list:
            student_ans = next((j for j in soal.jawaban if j.student_id == student_id), None)

            ans_dto = None
            if student_ans:
                ans_dto = QuestionAnswerStudentResponse.model_validate(student_ans)

            q_dto = QuizRequestQuestionStudentResponse(
                id=soal.id,
                stimulus=QuestionStimulusStudentResponse.model_validate(soal.stimulus) if soal.stimulus else None,
                question_text=soal.question_text,
                kesimpulan=soal.kesimpulan,
                options=[QuestionOptionResponse.model_validate(o) for o in soal.opsi],
                answer=ans_dto,
            )
            questions_payload.append(q_dto.model_dump(mode="json"))

        async def event_generator() -> AsyncGenerator[str, None]:
            init_data = json.dumps({
                "type": "INIT",
                "questions": questions_payload,
                "target_end_time": target_end_time.isoformat(),
            })
            yield f"data: {init_data}\n\n"

            while True:
                current_now = datetime.now(timezone.utc)
                remaining_seconds = int((target_end_time - current_now).total_seconds())

                is_done = await self.progress_repo.check_is_quiz_done(student_id, quiz_id)

                if is_done or remaining_seconds <= 0:
                    finish_payload = json.dumps({"type": "FINISHED", "message": "Quiz submission completed."})
                    yield f"data: {finish_payload}\n\n"

                    await self.progress_repo.mark_quiz_completed(student_id, quiz_id)
                    await process_exam_review_task.kiq(quiz_id=quiz_id, student_id=student_id)
                    break

                minutes, seconds = divmod(remaining_seconds, 60)
                formatted_time = f"{minutes:02d}:{seconds:02d}"

                tick_payload = json.dumps({
                    "type": "TICK",
                    "time": formatted_time,
                    "remaining_seconds": remaining_seconds,
                })
                yield f"data: {tick_payload}\n\n"
                await asyncio.sleep(1)

        return event_generator()

    async def submit_answer(self, soal_id: int, student_id: int, payload: SoalSubmitRequest) -> None:
        """Simpan jawaban dan langkah pengerjaan siswa; evaluasi jawaban salah dijalankan saat hasil kuis diminta (EvaluaizerService)."""
        soal = await self.soal_repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")

        progress = await self.progress_repo.get_quiz_progress(soal.quiz_request_id, student_id)
        if not progress or progress.is_done:
            raise BadRequestException("Sesi kuis telah selesai, jawaban tidak dapat diubah.")

        quiz = await self.repo.get_quiz_request(soal.quiz_request_id)
        if quiz is not None and progress.started_at is not None:
            deadline = min(progress.started_at + timedelta(minutes=quiz.max_duration_minutes), quiz.end_time)
            if datetime.now(timezone.utc) > deadline + SUBMIT_GRACE:
                raise BadRequestException("Waktu pengerjaan kuis telah habis, jawaban tidak dapat diubah.")

        existing = await self.progress_repo.get_soal_jawaban(soal_id, student_id)
        is_correct = payload.selected_option.upper() == soal.correct_option.upper()

        if existing is not None:
            try:
                self.progress_repo.update_soal_jawaban(
                    jawaban_id=existing.id,
                    selected_option=payload.selected_option,
                    is_correct=is_correct,
                )
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e
        else:
            try:
                await self.db.commit()
                await self.progress_repo.create_soal_jawaban(soal_id, student_id, payload.selected_option, is_correct)
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e

    async def finish_and_enqueue_review(self, quiz_id: int, student_id: int) -> None:
        progress = await self.progress_repo.get_quiz_progress(quiz_id, student_id)
        if not progress:
            raise NotFoundException("Sesi kuis tidak ditemukan")

        if progress.is_done:
            return

        await self.progress_repo.mark_quiz_completed(student_id, quiz_id)
        await process_exam_review_task.kiq(quiz_id, student_id)

    async def add_step(self, dto: AddStepRequest, soal_id: int, student_id: int) -> QuestionStudentSteps:
        try:
            row_data = await self.progress_repo.add_step(soal_id, student_id, dto.step)
            step_model = QuestionStudentSteps.model_validate(row_data)
            await self.db.commit()
            return step_model
        except Exception as e:
            await self.db.rollback()
            raise e

    async def delete_step(self, step_id: int, student_id: int):
        try:
            success = await self.progress_repo.remove_step(step_id, student_id)

            if not success:
                await self.db.rollback()
                return False

            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            raise e

    async def _ensure_student_in_classroom(self, student_id: int, classroom_id: int) -> None:
        if not await self.quiz_repo.is_student_in_classroom(student_id, classroom_id):
            raise ForbiddenException("Anda tidak terdaftar di kelas ini.")
