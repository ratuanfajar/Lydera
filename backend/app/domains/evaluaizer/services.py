from datetime import datetime, timedelta, timezone

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.evaluaizer.evaluation import AnswerEvaluator, needs_evaluation
from app.domains.quizzer.models import SoalJawaban
from app.domains.quizzer.models.quiz_progress import QuizReviewStatus
from app.domains.quizzer.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface
from app.domains.quizzer.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizzer.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizzer.schemas import LetakKesalahan, QuizResultItem
from app.domains.quizzer.schemas.soal_jawaban import SoalJawabanLangkahResponse
from app.tasks.process_exam_review_tasks import process_exam_review_task
from app.domains.quizzer.schemas.quiz_request_query import QuizRequestStudentDetailQuery
from backend.app.domains.quizzer.schemas.soal_response import SoalOpsiResponse


class EvaluaizerService:
    def __init__(self, quiz_req_repo: QuizRequestRepositoryInterface, quiz_prog_repo: QuizProgressRepositoryInterface, quiz_soal_repo: SoalRepositoryInterface, evaluator: AnswerEvaluator):
        self.quiz_soal_repo = quiz_soal_repo
        self.quiz_prog_repo = quiz_prog_repo
        self.quiz_req_repo = quiz_req_repo
        self.evaluator = evaluator

    async def get_student_quiz_result_from_teacher(self, quiz_request_id: int, query: QuizRequestStudentDetailQuery, teacher_id: int):
        is_valid = await self.quiz_req_repo.validate_quiz_request(quiz_request_id, teacher_id, query.classroom_id)
        if not is_valid:
            raise ForbiddenException("Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")
    
        return await self.get_quiz_results(quiz_request_id, query.student_id)

    async def get_quiz_results(self, quiz_request_id: int, student_id: int) -> list[QuizResultItem]:
        """Hasil kuis siswa; jawaban salah yang belum dievaluasi dievaluasi sekarang kecuali proses lain sedang mengerjakannya."""
        quiz_request = await self.quiz_req_repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("Quiz request tidak ditemukan.")

        progress = await self.quiz_prog_repo.get_quiz_progress(quiz_request_id, student_id)
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
                await self.quiz_req_repo.refresh_quiz_progress(progress)

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
            await self.quiz_req_repo.refresh_quiz_progress(progress)

        if not progress or not progress.is_done or progress.review_status != QuizReviewStatus.COMPLETED:
            raise BadRequestException("Kuis belum selesai dikerjakan atau hasil belum siap.")

        evaluation = await self.evaluator.evaluate(quiz_request_id, student_id)

        soal_list = await self.quiz_soal_repo.get_soal_for_request(quiz_request_id)
        jawaban_list = await self.quiz_prog_repo.get_jawaban_for_request(quiz_request_id, student_id)
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
                options=[SoalOpsiResponse(label=o.label, opsi_text=o.opsi_text) for o in sorted(soal.opsi, key=lambda o: o.label)],
                question_text=soal.question_text,
                selected_option=jawaban.selected_option if jawaban else None,
                correct_option=soal.correct_option,
                kesimpulan=soal.kesimpulan,
                langkah_kunci=[l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
                is_correct=jawaban.is_correct if jawaban else None,
                letak_kesalahan=_letak_kesalahan(jawaban),
                evaluasi_gagal=failed,
                evaluasi_diproses=processing,
                langkah=[
                    SoalJawabanLangkahResponse.model_validate(step)
                        for step in (jawaban.langkah if jawaban and jawaban.langkah else [])
                ],
            ))
        return results


def _letak_kesalahan(jawaban: SoalJawaban | None) -> LetakKesalahan | None:
    if jawaban is None or jawaban.is_correct or jawaban.evaluated_at is None or jawaban.letak_dapat_ditentukan is None:
        return None
    return LetakKesalahan(
        dapat_ditentukan=jawaban.letak_dapat_ditentukan,
        langkah_ke=jawaban.divergence_step,
        kutipan=jawaban.letak_kutipan,
        keterangan=jawaban.diagnosis or "",
        perlu_ditinjau=jawaban.needs_review,
    )
