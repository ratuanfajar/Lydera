import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from redis.asyncio import Redis
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizzer.models import Soal

from app.domains.quizzer.models import Soal, SoalJawaban
from app.domains.quizzer.repositories.interface import QuizRepositoryInterface
from app.domains.quizzer.schemas import QuizResultItem, SoalJustification, SoalSubmitRequest

from app.domains.quizzer.models.quiz_request import QuizRequest, QuizRequestStatus
from app.domains.quizzer.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizzer.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.domains.quizzer.schemas.quiz_request_create import QuizRequestCreate
from app.utils.idempotency import generate_idempotency_key
from app.domains.quizzer.schemas.soal_create_request import SaveQuizRequestPayload
from app.domains.quizzer.schemas.quiz_request_update import QuizRequestUpdate
from app.domains.quizzer.schemas.quiz_request_student_query import QuizRequestStudentQuery
from app.domains.quizzer.schemas.quiz_request_student_response import QuestionAnswerStudentResponse, QuestionOptionResponse, QuestionStimulusStudentResponse, QuizRequestQuestionStudentResponse, QuizRequestStudentResponse
from app.domains.quizzer.models.quiz_progress import QuizReviewStatus
from app.tasks.process_exam_review_tasks import process_exam_review_task
from app.utils import paths

paths.setup()

from app.domains.quizzer.schemas.soal_jawaban import SoalJawabanLangkahResponse
from quizzer import quizzer_regenerate
from quizzer import readable as quizzer_readable
from quizzer import segment as quizzer_segment

TTL_3_MINUTES = 180
logger = logging.getLogger(__name__)


def _soal_to_dict(soal: Soal) -> dict:
    """Bentuk teks yang diedit LLM: markup bila soal punya rumus, selain itu teks biasa."""
    markup = soal.markup or {}
    return {
        "id": soal.id,
        "question_text": markup.get("question", soal.question_text),
        "options": markup.get("options") or {o.label: o.opsi_text for o in soal.opsi},
        "correct_option": soal.correct_option,
        "langkah": markup.get("langkah") or [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": markup.get("kesimpulan", soal.kesimpulan),
    }


def _review_dict(soal: Soal) -> dict:
    """Bentuk yang diverifikasi: teks siap-baca (yang didengar siswa) plus markup untuk audit kesetiaan."""
    return {
        "id": soal.id,
        "question_text": soal.question_text,
        "options": {o.label: o.opsi_text for o in soal.opsi},
        "correct_option": soal.correct_option,
        "langkah": [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": soal.kesimpulan,
        "markup": soal.markup,
        "stimulus": {"readable_text": soal.stimulus.readable_text, "source_markup": soal.stimulus.source_markup or ""} if soal.stimulus else None,
    }


def _readable_dict(soal: Soal) -> dict:
    return {
        "question": soal.question_text,
        "options": {o.label: o.opsi_text for o in soal.opsi},
        "langkah": [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": soal.kesimpulan,
    }


def _student_markup(soal: Soal) -> dict | None:
    markup = soal.markup
    return {k: markup[k] for k in ("question", "options") if k in markup} if markup else None


def _review_flags(issues: list[str]) -> tuple[str, str | None]:
    return ("high" if issues else "normal"), ("\n".join(issues) or None)


class QuizService:
    def __init__(self, repo: QuizRepositoryInterface, db: AsyncSession, redis:Redis):
        self.repo = repo
        self.db = db
        self.redis = redis

    async def delete_quiz(self, teacher_id:int, quiz_request_id:int, classroom_id:int):
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException("Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")

        deleted = await self.repo.delete_quizz(quiz_request_id)

        if not deleted:
            raise NotFoundException("Quiz request tidak ditemukan.")

        map_key = f"quiz_idem_map:{quiz_request_id}"
        idem_key = await self.redis.get(map_key)
        await self.db.commit()
        keys_to_delete = [
            f"quiz_result:{quiz_request_id}",
            f"quiz_stream:{quiz_request_id}",
            map_key,
        ]
        if idem_key:
            keys_to_delete.append(idem_key)

        await self.redis.delete(*keys_to_delete)
        return True

    # -- Write (dengan commit) --
    async def create_quiz_request(self, teacher_id: int, dto: QuizRequestCreate) -> tuple[int, str, bool, str]:
        """Validasi module/chapter, buat quiz_request + link tiap bab dengan target soal-nya sendiri.
        Pemrosesan sesungguhnya (generate + validate) dijalankan async lewat quiz_tasks.py."""
        chapter_dicts = [c.model_dump() for c in dto.chapters]
        chapter_ids = [c.chapter_id for c in dto.chapters]

        idem_key = generate_idempotency_key(
            teacher_id, dto.classroom_id, dto.module_id, dto.title, chapter_dicts, dto.max_duration_minutes, dto.max_retry,
            dto.start_time.isoformat(),
            dto.end_time.isoformat(),
        )

        cached_job = await self.redis.get(idem_key)
        if cached_job:
            await self.redis.expire(idem_key, TTL_3_MINUTES)
            data = json.loads(cached_job)
            return data["quiz_request_id"], data["status"], True, idem_key
        
        is_valid, err_msg = await self.repo.validate_ownership_and_hierarchy(
            teacher_id, dto.classroom_id, dto.module_id, chapter_ids
        )

        if not is_valid:
            raise BadRequestException(err_msg)

        try:
            quiz_request = await self.repo.create_quiz_request(dto.module_id, dto.title, classroom_id=dto.classroom_id, max_duration_minutes=dto.max_duration_minutes, max_retry=dto.max_retry,                                                        
                start_time=dto.start_time,
                end_time=dto.end_time)
            await self.repo.bulk_link_chapters(quiz_request, dto.chapters)
            await self.repo.db.commit()

        except Exception as e:
            await self.repo.db.rollback()
            raise e

        job_meta = {"quiz_request_id": quiz_request, "status": "queued"}
        await self.redis.set(idem_key, json.dumps(job_meta), ex=TTL_3_MINUTES)
        await self.redis.set(f"quiz_idem_map:{quiz_request}", idem_key, ex=TTL_3_MINUTES)

        return quiz_request, "queued", False, idem_key

    async def update_quiz_settings(
        self,
        teacher_id: int,
        classroom_id: int,
        quiz_request_id: int,
        dto: QuizRequestUpdate,
    ) -> QuizRequestTeacherDetailResponse:
        """
        Validates teacher authorization, merges partial updates with existing DB schedule 
        to guarantee schedule validity, updates DB record, and returns full details.
        """
        # 1. Validate teacher ownership and classroom hierarchy
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException(
                "Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses."
            )

        # 2. Fetch existing record to validate combined schedule state
        existing_quiz = await self.repo.get_quiz_request(quiz_request_id)
        if not existing_quiz:
            raise NotFoundException("Quiz request tidak ditemukan.")

        # Merge payload values with existing DB state for cross-field schedule validation
        final_start = dto.start_time or existing_quiz.start_time
        final_end = dto.end_time or existing_quiz.end_time
        final_duration = dto.max_duration_minutes or existing_quiz.max_duration_minutes

        if final_end <= final_start:
            raise BadRequestException("Waktu selesai (end_time) harus lebih besar dari waktu mulai.")

        window_minutes = (final_end - final_start).total_seconds() / 60.0
        if window_minutes < final_duration:
            raise BadRequestException(
                f"Rentang waktu kuis ({int(window_minutes)} menit) tidak boleh lebih pendek "
                f"dari durasi pengerjaan kuis ({final_duration} menit)."
            )

        # 3. Apply updates to DB
        updated_quiz = await self.repo.update_quiz_request_settings(
            quiz_request_id=quiz_request_id,
            title=dto.title,
            max_duration_minutes=dto.max_duration_minutes,
            start_time=dto.start_time,
            end_time=dto.end_time,
        )
        await self.repo.db.commit()

        # 4. Return updated quiz details
        return await self.get_quiz_teacher(
            QuizRequestDetailQuery(classroom_id=classroom_id),
            teacher_id=teacher_id,
            id=quiz_request_id,
        )

    async def update_publish_status(
        self,
        teacher_id: int,
        classroom_id: int,
        quiz_request_id: int,
        status: QuizRequestStatus,
    ) -> bool:
        """
        Validates ownership and updates the publication status of a quiz request.
        """
        # Validate that quiz_request_id exists and belongs to teacher & classroom
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException(
                "Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses."
            )

        updated = await self.repo.update_quiz_status_publish(
            quiz_request_id=quiz_request_id,
            status=status.value,
        )
        if not updated:
            raise NotFoundException("Quiz request tidak ditemukan.")
        await self.db.commit()

        return True

    async def save_and_finalize_quiz(
        self,
        teacher_id: int,
        quiz_request_id: int,
        payload: SaveQuizRequestPayload,
    ) -> bool:
        is_owner = await self.repo.validate_quiz_request(
        quiz_request_id=quiz_request_id,
        teacher_id=teacher_id,
        classroom_id=payload.classroom_id,
        )
        if not is_owner:
            raise ForbiddenException("Kelas tidak ditemukan atau Anda tidak memiliki akses ke kelas ini.")

        # map_key = f"quiz_idem_map:{quiz_request_id}"
        # idem_key = await self.redis.get(map_key)

        # keys_to_delete = [
        #     f"quiz_result:{quiz_request_id}",
        #     f"quiz_stream:{quiz_request_id}",
        #     map_key,
        # ]
        # if idem_key:
        #     keys_to_delete.append(idem_key)

        # await self.redis.delete(*keys_to_delete)
        return True

    async def _ensure_soal_owner(self, soal_id: int, teacher_id: int) -> None:
        if not await self.repo.validate_soal_owner(soal_id, teacher_id):
            raise ForbiddenException("Soal tidak ditemukan atau Anda tidak memiliki akses.")

    async def edit_soal(self, soal_id: int, teacher_id: int, payload) -> Soal:
        """Edit langsung (isi soal tidak ditulis LLM; sesudah simpan, validator memverifikasi ulang). Hanya berlaku untuk soal berdiri sendiri (stimulus_id kosong, biasanya LOTS)."""
        await self._ensure_soal_owner(soal_id, teacher_id)
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if soal.stimulus_id is not None:
            raise BadRequestException("soal ini punya stimulus, koreksi lewat POST /quizzer/teacher/soal/stimulus/regenerate/{soal_id}")

        touched = False
        try:
            text_fields = {
                "question": payload.question_text, "options": payload.options,
                "langkah": payload.langkah, "kesimpulan": payload.kesimpulan,
            }
            if payload.markup or any(value is not None for value in text_fields.values()):
                merged = {**_readable_dict(soal), **(soal.markup or {})}
                merged.update({key: value for key, value in text_fields.items() if value is not None})
                merged.update(payload.markup or {})
                problems = quizzer_readable.fields_issues(merged)
                if problems:
                    raise BadRequestException("Markup tidak valid: " + "; ".join(problems))
                try:
                    readable, markup = await asyncio.to_thread(quizzer_readable.derive_fields, merged)
                except Exception:
                    logger.exception("verbalisasi markup soal %s gagal", soal_id)
                    raise BadRequestException("Teks siap-baca tidak dapat dibuat dari markup ini, coba lagi.")
                soal.question_text = readable["question"]
                soal.kesimpulan = readable["kesimpulan"]
                soal.markup = markup
                await self.repo.replace_soal_opsi(soal_id, readable["options"])
                await self.repo.replace_soal_langkah(soal_id, readable["langkah"])
                touched = True
            if payload.correct_option is not None:
                soal.correct_option = payload.correct_option
                touched = True
            if touched:
                soal.review_status = "edited"

            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

        updated = await self.repo.get_soal_by_id(soal_id)
        if touched:
            await self._refresh_review_flags(updated)
            updated = await self.repo.get_soal_by_id(soal_id)
        return updated

    async def _refresh_review_flags(self, soal: Soal) -> None:
        """Verifikasi ulang soal yang diedit guru (jawab buta + audit) lalu perbarui tanda review; tidak pernah menggagalkan simpan."""
        try:
            blocks = await self.repo.get_blocks_for_chapter(soal.chapter_id)
            rows = [{"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text} for b in blocks]
            source_text = quizzer_segment.span_text(rows, soal.source_reading_order_start, soal.source_reading_order_end)
            stimulus_text = soal.stimulus.readable_text if soal.stimulus else ""
            issues = await asyncio.to_thread(quizzer_regenerate.review_soal, source_text, _review_dict(soal), stimulus_text)
        except Exception:
            logger.exception("verifikasi ulang soal %s gagal", soal.id)
            issues = ["Verifikasi otomatis gagal dijalankan; periksa soal ini secara manual."]
        soal.review_priority, soal.validation_notes = _review_flags(issues)
        await self.db.commit()

    async def regenerate_cluster(self, soal_id: int, teacher_id: int, feedback: str) -> list[Soal]:
        """Feedback guru untuk SATU soal memicu edit soal itu (bukan generate ulang dari nol --
        lihat `ai-services/quizzer/revise.py`). Kalau perbaikannya ternyata perlu sampai ke stimulus
        (shared ke soal lain di cluster), stimulus ikut direvisi dan SEMUA soal di cluster
        di-recheck konsistensinya -- kalau tidak, cuma soal yang dikritik yang tersentuh, stimulus
        dan soal lain di cluster tetap utuh. Guru approve draft hasilnya sebelum final --
        review_status dikembalikan ke 'pending', bukan otomatis final."""
        await self._ensure_soal_owner(soal_id, teacher_id)
        target_soal = await self.repo.get_soal_by_id(soal_id)
        if target_soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if target_soal.stimulus_id is None:
            raise BadRequestException("soal ini tidak punya stimulus, edit langsung lewat PATCH /soal/{id}")

        stimulus = await self.repo.get_stimulus_by_id(target_soal.stimulus_id)
        cluster = await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        sibling_soal = [s for s in cluster if s.id != soal_id]

        all_blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        blocks_as_rows = [
            {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
            for b in all_blocks
        ]

        try:
            result = await asyncio.to_thread(
                quizzer_regenerate.compute_regeneration,
                blocks_as_rows,
                target_soal.source_reading_order_start, target_soal.source_reading_order_end,
                stimulus.source_markup or "", stimulus.readable_text, _soal_to_dict(target_soal),
                [_soal_to_dict(s) for s in sibling_soal], feedback,
            )
        except Exception:
            logger.exception("regenerasi soal %s gagal", soal_id)
            raise BadRequestException("Regenerasi gagal, coba lagi.")
        
        try:
            if result["new_stimulus"]:
                await self.repo.update_stimulus_text(
                    stimulus, result["new_stimulus"]["readable_text"], result["new_stimulus"]["source_markup"],
                    result["new_stimulus"]["ringkasan"], result["new_stimulus"]["tabel"],
                )

            for sid, data, issues in result["soal_updates"]:
                soal = await self.repo.get_soal_by_id(sid)
                soal.question_text = data["question_text"]
                soal.markup = data.get("markup")
                soal.correct_option = data["correct_option"]
                soal.kesimpulan = data["kesimpulan"]
                soal.review_status = "pending"
                soal.review_priority, soal.validation_notes = _review_flags(issues)
                await self.repo.replace_soal_opsi(sid, data["options"])
                await self.repo.replace_soal_langkah(sid, data["langkah"])

            await self.db.commit()
            return await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        except Exception as e:
            await self.db.rollback()
            raise e
        
      # -- Read (tanpa commit) --
    
    async def get_soal(self, soal_id: int) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        return soal
    
    async def get_quizzes_teacher(self, query: QuizRequestQuery, teacher_id:int) -> list[QuizRequestTeacherResponse]:
        quizzes = await self.repo.get_quizzes_teacher(query.classroom_id, teacher_id, query.status)
        return [QuizRequestTeacherResponse.model_validate(q) for q in quizzes]

    async def _ensure_student_in_classroom(self, student_id: int, classroom_id: int) -> None:
        if not await self.repo.is_student_in_classroom(student_id, classroom_id):
            raise ForbiddenException("Anda tidak terdaftar di kelas ini.")

    async def get_quizzes_student(self, query: QuizRequestStudentQuery, student_id:int) -> list[QuizRequestStudentResponse]:
        await self._ensure_student_in_classroom(student_id, query.classroom_id)
        quizzes = await self.repo.get_quizzes_student(query.classroom_id, student_id, query.status)
        return [QuizRequestStudentResponse.model_validate(q) for q in quizzes]

    async def get_quiz_teacher(self, query: QuizRequestDetailQuery, teacher_id:int, id:int) -> QuizRequestTeacherDetailResponse: 
        quiz = await self.repo.get_quiz_teacher(query.classroom_id, teacher_id, id)
        if not quiz:
            raise NotFoundException(
                "Quiz tidak ditemukan"
            )
        return QuizRequestTeacherDetailResponse.model_validate(quiz)

    # -- Jawaban siswa --
    async def initialize_and_stream_quiz(self, student_id:int, quiz_id:int) -> AsyncGenerator[str, None]:
        now = datetime.now(timezone.utc)
        quiz = await self.repo.get_quiz_request(quiz_id)
        if quiz is None or quiz.status_published != QuizRequestStatus.PUBLISH:
            raise NotFoundException("Kuis tidak ditemukan.")
        await self._ensure_student_in_classroom(student_id, quiz.classroom_id)
        quiz, progress = await self.repo.get_or_create_quiz_progress(student_id, quiz_id)

        if now < quiz.start_time or now > quiz.end_time:
            raise BadRequestException("Sesi kuis tidak sedang aktif.")

        if progress.is_done:
            raise BadRequestException("Kuis ini telah selesai dikerjakan.")

        session_active = False
        if progress.started_at is not None:
            session_duration = timedelta(minutes=quiz.max_duration_minutes)
            session_deadline = min(progress.started_at + session_duration, quiz.end_time)

            if now < session_deadline:
                session_active = True

        if not session_active:
            if progress.attempt_count >= quiz.max_retry:
                raise BadRequestException("Anda telah mencapai batas maksimal percobaan kuis")

            progress.attempt_count += 1
            progress.started_at = now
            await self.repo.db.commit()

        target_end_time = min(
            progress.started_at + timedelta(minutes=quiz.max_duration_minutes),
            quiz.end_time
        )

        # -------------------------------------------------------------
        # 1. FETCH & MAP QUESTIONS DATA FOR FIRST SSE EVENT
        # -------------------------------------------------------------
        soal_list = await self.repo.get_quiz_questions_with_answers(quiz_id, student_id)
        questions_payload = []
        for soal in soal_list:
            # Extract student answer for this question
            student_ans = next((j for j in soal.jawaban if j.student_id == student_id), None)
            
            ans_dto = None
            if student_ans:
                ans_dto = QuestionAnswerStudentResponse.model_validate(student_ans)

            q_dto = QuizRequestQuestionStudentResponse(
                id=soal.id,
                stimulus=QuestionStimulusStudentResponse.model_validate(soal.stimulus) if soal.stimulus else None,
                question_text=soal.question_text,
                markup=_student_markup(soal),
                options=[QuestionOptionResponse.model_validate(o) for o in soal.opsi],
                answer=ans_dto,
            )
            questions_payload.append(q_dto.model_dump(mode="json"))

        async def event_generator() -> AsyncGenerator[str, None]:
            # -------------------------------------------------------------
            # 2. EMIT FIRST EVENT: INITIAL DATA (QUESTIONS & CONFIG)
            # -------------------------------------------------------------
            init_data = json.dumps({
                "type": "INIT",
                "questions": questions_payload,
                "target_end_time": target_end_time.isoformat(),
            })
            yield f"data: {init_data}\n\n"

            # -------------------------------------------------------------
            # 3. COUNTDOWN STREAM LOOP
            # -------------------------------------------------------------
            while True:
                current_now = datetime.now(timezone.utc)
                remaining_seconds = int((target_end_time - current_now).total_seconds())

                is_done = await self.repo.check_is_quiz_done(student_id, quiz_id)

                if is_done or remaining_seconds <= 0:
                    finish_payload = json.dumps({"type": "FINISHED", "message": "Quiz submission completed."})
                    yield f"data: {finish_payload}\n\n"
                    
                    await self.repo.mark_quiz_completed(student_id, quiz_id)
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

    def _are_steps_equal(self, existing_langkah: list, new_langkah: list) -> bool:
        """Helper to check if student's step-by-step submission remains unchanged."""
        if len(existing_langkah) != len(new_langkah):
            return False
        for old, new in zip(existing_langkah, new_langkah):
            if getattr(old, "urutan", None) != new.urutan or getattr(old, "teks", None) != new.teks:
                return False
        return True
    
    async def submit_answer(self, soal_id: int, student_id: int, payload: SoalSubmitRequest) -> None:
        """Simpan jawaban dan langkah pengerjaan siswa; evaluasi jawaban salah dijalankan saat hasil kuis diminta (EvaluaizerService)."""
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")

        progress = await self.repo.get_quiz_progress(soal.quiz_request_id, student_id)
        if not progress or progress.is_done:
            raise BadRequestException("Sesi kuis telah selesai, jawaban tidak dapat diubah.")

        existing = await self.repo.get_soal_jawaban(soal_id, student_id)
        is_correct = payload.selected_option.upper() == soal.correct_option.upper()
        if existing is not None:
            try:
                await self.repo.update_soal_jawaban(
                    jawaban_id=existing.id,
                    selected_option=payload.selected_option,
                    is_correct=is_correct,
                    langkah=payload.langkah,
                )
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e
        else:
            try:
                await self.db.commit()
                await self.repo.create_soal_jawaban(soal_id, student_id, payload.selected_option, is_correct, payload.langkah)
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e

    async def finish_and_enqueue_review(self, quiz_id:int, student_id:int) -> None:
        progress = await self.repo.get_quiz_progress(quiz_id, student_id)
        if not progress:
            raise NotFoundException("Sesi kuis tidak ditemukan")

        if progress.is_done:
            return

        await self.repo.mark_quiz_completed(student_id, quiz_id)
        await process_exam_review_task.kiq(quiz_id, student_id)
