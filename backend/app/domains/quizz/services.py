import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from redis.asyncio import Redis
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizz.models import Soal

from app.domains.quizz.models import Soal, SoalJawaban
from app.domains.quizz.repositories.interface import QuizRepositoryInterface
from app.domains.quizz.schemas import QuizResultItem, SoalJustification, SoalSubmitRequest

from app.domains.quizz.models.quiz_request import QuizRequest, QuizRequestStatus
from app.domains.quizz.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizz.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.domains.quizz.schemas.quiz_request_create import QuizRequestCreate
from app.utils.idempotency import generate_idempotency_key
from app.domains.quizz.schemas.soal_create_request import SaveQuizRequestPayload
from app.domains.quizz.schemas.soal_regenerate import RegenerateClusterRequest
from app.domains.quizz.schemas.quiz_request_update import QuizRequestUpdate
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQuery
from app.domains.quizz.schemas.quiz_request_student_response import QuestionAnswerStudentResponse, QuestionOptionResponse, QuestionStimulusStudentResponse, QuizRequestQuestionStudentResponse, QuizRequestStudentResponse
from app.domains.quizz.models.quiz_progress import QuizReviewStatus
from app.tasks.process_exam_review_tasks import process_exam_review_task
import paths

paths.setup()

import evaluate as quiz_evaluate
import regenerate as quiz_regenerate
from segment import Segment

TTL_3_MINUTES = 180
class QuizService:
    def __init__(self, repo: QuizRepositoryInterface, db: AsyncSession, redis:Redis):
        self.repo = repo
        self.db = db
        self.redis = redis

    async def delete_quiz(self, teacher_id:int, quiz_request_id:int, classroom_id:int):
        if classroom_id:
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
            teacher_id, dto.classroom_id, dto.module_id, dto.title, chapter_dicts, dto.max_duration_minutes,
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
            quiz_request = await self.repo.create_quiz_request(dto.module_id, dto.title, classroom_id=dto.classroom_id, max_duration_minutes=dto.max_duration_minutes,
                start_time=dto.start_time,
                end_time=dto.end_time,)
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

    async def edit_soal(self, soal_id: int, payload) -> Soal:
        """Edit langsung tanpa LLM. Hanya berlaku untuk soal berdiri sendiri (stimulus_id kosong, biasanya LOTS)."""
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if soal.stimulus_id is not None:
            raise BadRequestException("soal ini punya stimulus, koreksi lewat POST /soal/{id}/regenerate")

        try:
            touched = False
            if payload.question_text is not None:
                soal.question_text = payload.question_text
                touched = True
            if payload.correct_option is not None:
                soal.correct_option = payload.correct_option
                touched = True
            if payload.kesimpulan is not None:
                soal.kesimpulan = payload.kesimpulan
                touched = True
            if payload.options is not None:
                await self.repo.replace_soal_opsi(soal_id, payload.options)
                touched = True
            if payload.langkah is not None:
                await self.repo.replace_soal_langkah(soal_id, payload.langkah)
                touched = True
            if touched:
                soal.review_status = "edited"

            await self.db.commit()
            return await self.repo.get_soal_by_id(soal_id)
        except Exception as e:
            await self.db.rollback()
            raise e

    async def regenerate_cluster(self, stimulus_id: int, feedback: str) -> list[Soal]:
        """Feedback guru memicu LLM meregenerasi satu cluster HOTS penuh (stimulus + semua soal yang
        berbagi stimulus itu). Guru approve draft hasilnya sebelum final -- review_status dikembalikan
        ke 'pending', bukan otomatis final."""
        stimulus = await self.repo.get_stimulus_by_id(stimulus_id)
        if stimulus is None:
            raise NotFoundException(f"stimulus_id={stimulus_id} tidak ditemukan")

        cluster = await self.repo.get_soal_by_stimulus(stimulus_id)
        if not cluster:
            raise NotFoundException(f"tidak ada soal untuk stimulus_id={stimulus_id}")

        all_blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        blocks_as_rows = [
            {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
            for b in all_blocks
        ]
        soal_bloom_levels = [(soal.id, soal.bloom_level) for soal in cluster]

        try:
            results = await asyncio.to_thread(
                quiz_regenerate.compute_cluster,
                stimulus.chapter_id, blocks_as_rows,
                stimulus.source_reading_order_start, stimulus.source_reading_order_end,
                soal_bloom_levels, feedback,
            )
        except Exception as exc:
            raise BadRequestException(f"regenerasi gagal, coba lagi: {exc}")
        
        try:
            new_stimulus_text = (results[0][1].get("stimulus") or {}).get("readable_text", "")
            if new_stimulus_text:
                await self.repo.update_stimulus_text(stimulus, new_stimulus_text)

            for soal_id, data, val in results:
                soal = await self.repo.get_soal_by_id(soal_id)
                soal.question_text = data["question_text"]
                soal.correct_option = data["correct_option"]
                soal.kesimpulan = data["kesimpulan"]
                soal.review_status = "pending"
                soal.review_priority = "normal" if val["matches"] else "high"
                soal.validation_notes = None
                if not val["matches"]:
                    soal.validation_notes = (
                        f"Validasi independen sampai ke jawaban {val['derived_option']}, berbeda dari "
                        f"jawaban Generation ({data['correct_option']})."
                    )
                await self.repo.replace_soal_opsi(soal_id, data["options"])
                await self.repo.replace_soal_langkah(soal_id, data["langkah"])

            await self.db.commit()
            return await self.repo.get_soal_by_stimulus(stimulus_id)
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

    async def get_quizzes_student(self, query: QuizRequestStudentQuery, student_id:int) -> list[QuizRequestStudentResponse]:
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
                kesimpulan=soal.kesimpulan,
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
        """Simpan jawaban + langkah pengerjaan siswa untuk satu soal. Tidak ada panggilan LLM di
        sini -- evaluasi (untuk yang salah) baru dijalankan saat siswa minta hasil akhir kuis lewat
        `get_quiz_results`. Satu siswa cuma bisa submit sekali per soal (unique constraint DB)."""
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")

        progress = await self.repo.get_quiz_progress(soal.quiz_request_id, student_id)
        if not progress or progress.is_done:
            raise BadRequestException("Sesi kuis telah selesai, jawaban tidak dapat diubah.")

        existing = await self.repo.get_soal_jawaban(soal_id, student_id)
        is_correct = payload.selected_option.upper() == soal.correct_option.upper()
        if existing is not None:
            if existing.selected_option == payload.selected_option and self._are_steps_equal(existing.langkah, payload.langkah):
                return
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

    async def get_quiz_results(self, quiz_request_id: int, student_id: int) -> list[QuizResultItem]:
        """Hasil kuis siswa untuk satu quiz_request: tiap soal yang dijawab SALAH dan belum pernah
        dievaluasi dipicu evaluasinya sekarang (paralel), lalu hasilnya disimpan supaya panggilan
        berikutnya tidak memanggil LLM ulang (`evaluated_at` jadi penanda sudah final)."""
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
                progress = await self.repo.get_quiz_progress(quiz_request_id, student_id)

        # -------------------------------------------------------------
        # EDGE CASE 2: Server Restart / Taskiq Job Crash Recovery
        # If task gets stuck in 'PROCESSING' > 3 mins or 'FAILED', run evaluation inline
        # -------------------------------------------------------------
        is_stuck = (
            progress 
            and progress.review_status == QuizReviewStatus.PROCESSING
            and progress.completed_at is None 
            and (now - (progress.started_at or now)) > timedelta(minutes=3)
        )
        if progress and (progress.review_status == QuizReviewStatus.FAILED or is_stuck):
            await process_exam_review_task(quiz_request_id, student_id)
            progress = await self.repo.get_quiz_progress(quiz_request_id, student_id)

        if not progress or not progress.is_done or progress.review_status != QuizReviewStatus.COMPLETED:
            raise BadRequestException("Kuis belum selesai dikerjakan atau hasil belum siap.")

        # -------------------------------------------------------------
        # FETCH SOAL & JAWABAN
        # -------------------------------------------------------------
        soal_list = await self.repo.get_soal_for_request(quiz_request_id)
        jawaban_list = await self.repo.get_jawaban_for_request(quiz_request_id, student_id)
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
                    await self.repo.save_evaluation(
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
            if jawaban is not None and not jawaban.is_correct:
                justification = SoalJustification(
                    divergence_step=jawaban.divergence_step,
                    diagnosis=jawaban.diagnosis or "",
                    personalized_justification=jawaban.personalized_justification or "",
                )
            results.append(QuizResultItem(
                soal_id=soal.id,
                question_text=soal.question_text,
                selected_option=jawaban.selected_option if jawaban else None,
                correct_option=soal.correct_option,
                is_correct=jawaban.is_correct if jawaban else None,
                justification=justification,
            ))
        return results

    async def _evaluate_one(self, soal: Soal, jawaban: SoalJawaban) -> dict:
        """Bangun Segment sumber dari rentang block soal ini, lalu jalankan Chain 5 di thread
        terpisah (sama seperti `regenerate_cluster` memanggil `compute_cluster`)."""
        blocks = await self.repo.get_blocks_for_chapter(soal.chapter_id)
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
