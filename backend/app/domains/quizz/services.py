import asyncio
from redis.asyncio import Redis
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizz.models import Soal
from app.domains.quizz.repositories.interface import QuizRepositoryInterface

from app.domains.quizz.models.quiz_request import QuizRequest, QuizRequestStatus
from app.domains.quizz.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizz.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.domains.quizz.schemas.quiz_request_create import QuizRequestCreate
from app.utils.idempotency import generate_idempotency_key
from app.domains.quizz.schemas.soal_create_request import SaveQuizRequestPayload
from app.domains.quizz.schemas.soal_regenerate import RegenerateClusterRequest
from app.domains.quizz.schemas.quiz_request_update import QuizRequestUpdate
import paths

paths.setup()

import regenerate as quiz_regenerate

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

    async def set_review_status(self, soal_id: int, status: str) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        try:
            await self.repo.set_review_status(soal, status)
            await self.db.commit()
            return soal
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

    async def regenerate_cluster_from_input(self, payload: RegenerateClusterRequest) -> dict:
        """
        Regenerates a HOTS cluster (stimulus + questions) based entirely on user input.
        Only fetches chapter text blocks from the database.
        """
        # 1. Fetch chapter blocks from DB (Chapter text blocks always exist after module upload)
        all_blocks = await self.repo.get_blocks_for_chapter(payload.chapter_id)
        if not all_blocks:
            raise NotFoundException(f"Teks modul untuk chapter_id={payload.chapter_id} tidak ditemukan")

        blocks_as_rows = [
            {
                "reading_order": b.reading_order,
                "block_type": b.block_type,
                "readable_text": b.readable_text,
            }
            for b in all_blocks
        ]

        # 2. Map items to (soal_id/temp_id, bloom_level) tuples expected by compute_cluster
        soal_bloom_levels = [(item.id, item.bloom_level) for item in payload.items]

        # 3. Call LLM regeneration in a thread pool
        try:
            results = await asyncio.to_thread(
                quiz_regenerate.compute_cluster,
                payload.chapter_id,
                blocks_as_rows,
                payload.stimulus.source_reading_order_start,
                payload.stimulus.source_reading_order_end,
                soal_bloom_levels,
                payload.feedback,
            )
        except Exception as exc:
            raise BadRequestException(f"Regenerasi gagal, coba lagi: {exc}")

        # 4. Format preview results
        new_stimulus_text = (results[0][1].get("stimulus") or {}).get("readable_text", "")

        preview_cluster = {
            "stimulus_text": new_stimulus_text,
            "soal_list": []
        }

        for soal_id, data, val in results:
            validation_notes = None
            if not val["matches"]:
                validation_notes = (
                    f"Validasi independen sampai ke jawaban {val['derived_option']}, berbeda dari "
                    f"jawaban Generation ({data['correct_option']})."
                )

            preview_cluster["soal_list"].append({
                "soal_id": soal_id,
                "question_text": data["question_text"],
                "correct_option": data["correct_option"],
                "kesimpulan": data["kesimpulan"],
                "review_status": "pending",
                "review_priority": "normal" if val["matches"] else "high",
                "validation_notes": validation_notes,
                "options": data["options"],
                "langkah": data["langkah"],
            })

        return preview_cluster
    # -- Read (tanpa commit) --
    async def get_quiz_request_status(self, quiz_request_id: int):
        quiz_request = await self.repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("quiz_request tidak ditemukan")
        return quiz_request

    async def list_soal_for_request(self, quiz_request_id: int) -> list[Soal]:
        return await self.repo.get_soal_for_request(quiz_request_id)

    async def get_soal(self, soal_id: int) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        return soal

    async def get_quizzes_teacher(self, query: QuizRequestQuery, teacher_id:int) -> list[QuizRequestTeacherResponse]:
        quizzes = await self.repo.get_quizzes_teacher(query.classroom_id, teacher_id, query.status)
        return [QuizRequestTeacherResponse.model_validate(q) for q in quizzes]

    async def get_quiz_teacher(self, query: QuizRequestDetailQuery, teacher_id:int, id:int) -> QuizRequestTeacherDetailResponse: 
        quiz = await self.repo.get_quiz_teacher(query.classroom_id, teacher_id, id)
        if not quiz:
            raise NotFoundException(
                "Quiz tidak ditemukan"
            )
        return QuizRequestTeacherDetailResponse.model_validate(quiz)