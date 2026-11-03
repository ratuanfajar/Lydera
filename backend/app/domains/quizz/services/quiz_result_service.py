import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizz.models import Soal, SoalJawaban
from app.domains.quizz.models.quiz_progress import QuizReviewStatus
from app.domains.quizz.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface
from app.domains.quizz.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizz.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizz.schemas import QuizResultItem, SoalJustification
from app.domains.quizz.schemas.quiz_request_query import QuizRequestStudentDetailQuery
from app.domains.quizz.schemas.soal_jawaban import SoalJawabanLangkahResponse
from app.domains.quizz.schemas.soal_response import SoalOpsiResponse
from app.tasks.process_exam_review_tasks import process_exam_review_task
from app.utils import paths
paths.setup()
from quiz import evaluate as quiz_evaluate
from quiz.segment import Segment


class QuizResultService:
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

    async def get_student_quiz_result_from_teacher(self, quiz_request_id: int, query: QuizRequestStudentDetailQuery, teacher_id: int):
        is_valid = await self.quiz_repo.validate_quiz_request(quiz_request_id, teacher_id, query.classroom_id)
        if not is_valid:
            raise ForbiddenException("Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")

        return await self.get_quiz_results(quiz_request_id, query.student_id)

    async def get_quiz_results(self, quiz_request_id: int, student_id: int) -> list[QuizResultItem]:
        """Hasil kuis siswa untuk satu quiz_request: tiap soal yang dijawab SALAH dan belum pernah
        dievaluasi dipicu evaluasinya sekarang (paralel), lalu hasilnya disimpan."""
        quiz_request = await self.quiz_repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("Quiz request tidak ditemukan.")

        progress = await self.progress_repo.get_quiz_progress(quiz_request_id, student_id)
        now = datetime.now(timezone.utc)

        if progress and progress.started_at and not progress.is_done:
            deadline = min(
                progress.started_at + timedelta(minutes=quiz_request.max_duration_minutes),
                quiz_request.end_time,
            )
            if now >= deadline:
                await process_exam_review_task(quiz_request_id, student_id)
                progress = await self.progress_repo.get_quiz_progress(quiz_request_id, student_id)

        is_stuck = (
            progress
            and progress.review_status == QuizReviewStatus.PROCESSING
            and progress.completed_at is None
            and (now - (progress.started_at or now)) > timedelta(minutes=3)
        )
        if progress and (progress.review_status == QuizReviewStatus.FAILED or is_stuck):
            await process_exam_review_task(quiz_request_id, student_id)
            progress = await self.progress_repo.get_quiz_progress(quiz_request_id, student_id)

        if not progress or not progress.is_done or progress.review_status != QuizReviewStatus.COMPLETED:
            raise BadRequestException("Kuis belum selesai dikerjakan atau hasil belum siap.")

        soal_list = await self.soal_repo.get_soal_for_request(quiz_request_id)
        jawaban_list = await self.progress_repo.get_jawaban_for_request(quiz_request_id, student_id)
        jawaban_by_soal = {j.soal_id: j for j in jawaban_list}

        to_evaluate: list[tuple[Soal, SoalJawaban]] = []
        for soal in soal_list:
            jawaban = jawaban_by_soal.get(soal.id)
            if jawaban is not None and not jawaban.is_correct and jawaban.evaluated_at is None:
                to_evaluate.append((soal, jawaban))

        if to_evaluate:
            evaluations = await asyncio.gather(*[
                self._evaluate_one(soal, jawaban) for soal, jawaban in to_evaluate
            ])
            try:
                for (_, jawaban), result in zip(to_evaluate, evaluations):
                    await self.progress_repo.save_evaluation(
                        jawaban, result.get("divergence_step"),
                        result.get("diagnosis", ""), result.get("personalized_justification", ""),
                    )
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e

        results = []
        for soal in soal_list:
            jawaban = jawaban_by_soal.get(soal.id)
            justification = None
            if jawaban is not None:
                jawaban.langkah
            if jawaban is not None and not jawaban.is_correct:
                justification = SoalJustification(
                    divergence_step=jawaban.divergence_step,
                    diagnosis=jawaban.diagnosis or "",
                    personalized_justification=jawaban.personalized_justification or "",
                )
            results.append(QuizResultItem(
                soal_id=soal.id,
                options=[SoalOpsiResponse(label=o.label, opsi_text=o.opsi_text) for o in sorted(soal.opsi, key=lambda o: o.label)],
                question_text=soal.question_text,
                selected_option=jawaban.selected_option if jawaban else None,
                correct_option=soal.correct_option,
                is_correct=jawaban.is_correct if jawaban else None,
                justification=justification,
                langkah=[
                    SoalJawabanLangkahResponse.model_validate(step)
                    for step in (jawaban.langkah if jawaban and jawaban.langkah else [])
                ]
            ))
        return results

    async def _evaluate_one(self, soal: Soal, jawaban: SoalJawaban) -> dict:
        blocks = await self.soal_repo.get_blocks_for_chapter(soal.chapter_id)
        seg_blocks = [b for b in blocks if soal.source_reading_order_start <= b.reading_order <= soal.source_reading_order_end]
        seg = Segment(
            chapter_id=soal.chapter_id,
            title="",
            reading_order_start=soal.source_reading_order_start,
            reading_order_end=soal.source_reading_order_end,
            text="\n".join(b.readable_text for b in seg_blocks),
        )
        options = {o.label: o.opsi_text for o in soal.opsi}
        correct_langkah = [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)]
        student_langkah = [l.teks for l in sorted(jawaban.langkah, key=lambda l: l.urutan)]
        return await asyncio.to_thread(
            quiz_evaluate.evaluate_scratchwork,
            seg, soal.question_text, options, soal.correct_option, correct_langkah, soal.kesimpulan,
            jawaban.selected_option, student_langkah,
        )
