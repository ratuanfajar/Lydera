from datetime import datetime, timedelta, timezone

from app.core.exceptions import BadRequestException, NotFoundException
from app.domains.evaluaizer.evaluation import AnswerEvaluator, needs_evaluation
from app.domains.quizzer.models import SoalJawaban
from app.domains.quizzer.models.quiz_progress import QuizReviewStatus
from app.domains.quizzer.repositories.interface import QuizRepositoryInterface
from app.domains.quizzer.schemas import JustificationPoint, QuizResultItem, SoalJustification
from app.domains.quizzer.schemas.soal_jawaban import SoalJawabanLangkahResponse
from app.tasks.process_exam_review_tasks import process_exam_review_task


class EvaluaizerService:
    def __init__(self, repo: QuizRepositoryInterface, evaluator: AnswerEvaluator):
        self.repo = repo
        self.evaluator = evaluator

    async def get_quiz_results(self, quiz_request_id: int, student_id: int) -> list[QuizResultItem]:
        """Hasil kuis siswa; jawaban salah yang belum dievaluasi dievaluasi sekarang kecuali proses lain sedang mengerjakannya."""
        quiz_request = await self.repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("Quiz request tidak ditemukan.")

        progress = await self.repo.get_quiz_progress(quiz_request_id, student_id)
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # EDGE CASE 1: Lazy Finalization if student closed SSE timer
        # -------------------------------------------------------------
        if progress and progress.started_at and not progress.is_done:
            deadline = min(
                progress.started_at + timedelta(minutes=quiz_request.max_duration_minutes),
                quiz_request.end_time,
            )
            if now >= deadline:
                # Trigger grading immediately
                await process_exam_review_task(quiz_request_id, student_id)
                await self.repo.refresh_quiz_progress(progress)

        # -------------------------------------------------------------
        # EDGE CASE 2: Server Restart / Taskiq Job Crash Recovery
        # If task gets stuck in 'PROCESSING' > 3 mins or 'FAILED', run evaluation inline
        # -------------------------------------------------------------
        is_stuck = (
            progress 
            and progress.review_status == QuizReviewStatus.PROCESSING
            and progress.completed_at is None
            and (progress.review_started_at is None or (now - progress.review_started_at) > timedelta(minutes=3))
        )
        if progress and (progress.review_status == QuizReviewStatus.FAILED or is_stuck):
            await process_exam_review_task(quiz_request_id, student_id)
            await self.repo.refresh_quiz_progress(progress)

        if not progress or not progress.is_done or progress.review_status != QuizReviewStatus.COMPLETED:
            raise BadRequestException("Kuis belum selesai dikerjakan atau hasil belum siap.")

        evaluation = await self.evaluator.evaluate(quiz_request_id, student_id)

        soal_list = await self.repo.get_soal_for_request(quiz_request_id)
        jawaban_list = await self.repo.get_jawaban_for_request(quiz_request_id, student_id)
        jawaban_by_soal = {j.soal_id: j for j in jawaban_list}

        failed_ids = set(evaluation.failed)
        if evaluation.busy:
            failed_ids |= await self.evaluator.recent_failures([j.id for j in jawaban_list if needs_evaluation(j)])

        results = []
        for soal in soal_list:
            jawaban = jawaban_by_soal.get(soal.id)
            failed = jawaban is not None and jawaban.id in failed_ids
            processing = jawaban is not None and evaluation.busy and not failed and needs_evaluation(jawaban)
            results.append(QuizResultItem(
                soal_id=soal.id,
                question_text=soal.question_text,
                selected_option=jawaban.selected_option if jawaban else None,
                correct_option=soal.correct_option,
                kesimpulan=soal.kesimpulan,
                langkah_kunci=[l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
                is_correct=jawaban.is_correct if jawaban else None,
                justification=_justification(jawaban),
                evaluasi_gagal=failed,
                evaluasi_diproses=processing,
                langkah=[
                    SoalJawabanLangkahResponse.model_validate(step)
                        for step in (jawaban.langkah if jawaban and jawaban.langkah else [])
                ],
            ))
        return results


def _justification(jawaban: SoalJawaban | None) -> SoalJustification | None:
    if jawaban is None or jawaban.is_correct or needs_evaluation(jawaban):
        return None
    return SoalJustification(
        divergence_step=jawaban.divergence_step,
        error_type=jawaban.error_type,
        diagnosis=jawaban.diagnosis or "",
        points=[JustificationPoint(**point) for point in (jawaban.justification_points or [])],
        personalized_justification=jawaban.personalized_justification or "",
        perlu_ditinjau=jawaban.needs_review,
    )
