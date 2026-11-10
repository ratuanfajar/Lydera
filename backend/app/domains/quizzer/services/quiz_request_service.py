import hashlib
import json
from typing import Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.contents.repositories.interfaces.module_interface import ModuleRepositoryInterface
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.quizzer.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizzer.models.quiz_request import QuizRequest, QuizRequestStatus
from app.domains.quizzer.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizzer.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.domains.quizzer.schemas.quiz_request_create import QuizRequestCreate
from app.domains.quizzer.schemas.soal_create_request import SaveQuizRequestPayload, SoalCreateRequest, SoalDataCreateRequest, StimulusCreateRequest
from app.domains.quizzer.schemas.quiz_request_update import QuizRequestUpdate
from app.domains.quizzer.schemas.quiz_request_student_query import QuizRequestStudentQuery, QuizRequestStudentQueryStatus
from app.domains.quizzer.schemas.quiz_request_student_response import QuizRequestStudentProgressResponse, QuizRequestStudentResponse
from app.domains.quizzer.schemas.student_quiz_response import StudentQuizResponse
from app.domains.users.schemas.profile_response import ProfileResponse
from app.domains.users.schemas.student_response import StudentResponse
from app.domains.users.schemas.student_tasks_request import StudentTaskRequest
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.core.redis_keys import QuizRedisKeys
from app.domains.quizzer.schemas.create_quiz_request_result import CreateQuizRequestResult
from app.domains.quizzer.schemas.quiz_edit_response import QuizEditResponse
TTL_3_MINUTES = 180


class QuizRequestService:
    def __init__(
        self,
        repo: QuizRequestRepositoryInterface,
        content_repo: ModuleRepositoryInterface,
        db: AsyncSession,
        redis: Redis,
    ):
        self.repo = repo
        self.content_repo = content_repo
        self.db = db
        self.redis = redis

    def _build_soal_requests(self, cached_questions: list[dict]) -> list[SoalCreateRequest]:
        """Helper to reconstruct SoalCreateRequest objects from cached JSON dicts."""
        items_to_save: list[SoalCreateRequest] = []

        for item in cached_questions:
            data_dict = item.get("data", item)

            raw_options = data_dict.get("options", {})
            if isinstance(raw_options, list):
                options_dict = {
                    opt.get("label"): opt.get("opsi_text") or opt.get("text", "")
                    for opt in raw_options
                    if isinstance(opt, dict)
                }
            else:
                options_dict = raw_options

            raw_langkah = data_dict.get("langkah", [])
            langkah_list = [
                step.get("teks", "") if isinstance(step, dict) else step
                for step in raw_langkah
            ]

            stimulus_payload = None
            raw_stimulus = data_dict.get("stimulus")
            if raw_stimulus and isinstance(raw_stimulus, dict):
                stimulus_payload = StimulusCreateRequest(
                    source_markup=raw_stimulus.get("source_markup", ""),
                    readable_text=raw_stimulus.get("readable_text", ""),
                    source_reading_order_start=raw_stimulus.get("source_reading_order_start"),
                    source_reading_order_end=raw_stimulus.get("source_reading_order_end"),
                )

            data_payload = SoalDataCreateRequest(
                bloom_level=data_dict.get("bloom_level", 3),
                question_text=data_dict.get("question_text", ""),
                correct_option=data_dict.get("correct_option", ""),
                options=options_dict,
                langkah=langkah_list,
                kesimpulan=data_dict.get("kesimpulan", ""),
                reading_order_start=data_dict.get("reading_order_start", 0),
                reading_order_end=data_dict.get("reading_order_end", 0),
                stimulus=stimulus_payload,
            )

            items_to_save.append(
                SoalCreateRequest(
                    chapter_id=item.get("chapter_id"),
                    data=data_payload,
                    review_priority=item.get("review_priority", "normal"),
                    validation_notes=item.get("validation_notes"),
                )
            )

        return items_to_save

    async def create_quiz_request(self, teacher_id: int, dto: QuizRequestCreate, supplied_idem_key) -> CreateQuizRequestResult:
        chapter_ids = [c.chapter_id for c in dto.chapters]

        idem_digest, content_fingerprint = _generate_quiz_request_keys(
            teacher_id=teacher_id,
            dto=dto,
            supplied_idem_key=supplied_idem_key,
        )

        idem_key = QuizRedisKeys.idempotency(idem_digest)
        content_key = QuizRedisKeys.content(content_fingerprint)

        is_valid, err_msg = await self.repo.validate_ownership_and_hierarchy(
            teacher_id, dto.classroom_id, dto.module_id, chapter_ids
        )

        if not is_valid:
            raise BadRequestException(err_msg)

        # Prevent concurrent requests using the same idempotency identity.
        lock_key = QuizRedisKeys.lock(f"request:{idem_digest}")

        async with self.redis.lock(
            lock_key,
            timeout=30,
            blocking_timeout=10,
        ):
            existing_meta = await self.redis.get(idem_key)

            if existing_meta:
                metadata = json.loads(existing_meta)

                if metadata.get("status") in ("queued", "running"):
                    # Same active request: reuse its ID.
                    return CreateQuizRequestResult(
                        quiz_request_id=metadata["quiz_request_id"],
                        status=metadata["status"],
                        is_cached=False,
                        should_enqueue=False,
                        idem_digest=idem_digest,
                        content_fingerprint=content_fingerprint,
                    )
                await self.redis.delete(idem_key)

            cached_content = await self.redis.get(content_key)
            parsed_questions = None
            coverage_report = None

            if cached_content:
                cached_payload = json.loads(cached_content)

                # Current cache format:
                # {
                #     "questions": [...],
                #     "coverage_report": {...}
                # }
                #
                # List fallback supports the previous cache format.
                if isinstance(cached_payload, list):
                    parsed_questions = cached_payload
                else:
                    parsed_questions = cached_payload.get("questions", [])
                    coverage_report = cached_payload.get("coverage_report")
            try:
                quiz_request_id = await self.repo.create_quiz_request(
                    dto.module_id,
                    dto.title,
                    classroom_id=dto.classroom_id,
                    max_duration_minutes=dto.max_duration_minutes,
                    max_retry=dto.max_retry,
                    start_time=dto.start_time,
                    end_time=dto.end_time,
                )

                await self.repo.bulk_link_chapters(
                    quiz_request_id,
                    dto.chapters
                )

                if parsed_questions is not None:
                    items_to_save = self._build_soal_requests(parsed_questions)

                    if not items_to_save:
                        raise BadRequestException('Cached quiz content contains no valid questions.')

                    saved = await self.repo.save_quiz_data(
                        quiz_request_id,
                        dto.classroom_id,
                        'done',
                        items_to_save,
                        coverage_report
                    )

                    if not saved:
                        raise Exception(
                            f"Failed to save cached quiz: {quiz_request_id}"
                        )
                    
                await self.db.commit()
            except Exception:
                await self.db.rollback()
                raise

            if parsed_questions is not None:
                result_payload = {
                    "quiz_request_id": quiz_request_id,
                    "status": "done",
                    "completed": len(parsed_questions),
                    "total": len(parsed_questions),
                    "message": "Semua soal selesai dibuat (Cache Hit)",
                    "data": parsed_questions,
                    "coverage_report": coverage_report,
                }

                await self.redis.set(
                    QuizRedisKeys.result(quiz_request_id),
                    json.dumps(result_payload),
                    ex=TTL_3_MINUTES,
                )

                if coverage_report is not None:
                    await self.redis.set(
                        QuizRedisKeys.coverage(quiz_request_id),
                        json.dumps(coverage_report),
                        ex=TTL_3_MINUTES,
                    )

                return CreateQuizRequestResult(
                    quiz_request_id=quiz_request_id,
                    status="done",
                    is_cached=True,
                    should_enqueue=False,
                    idem_digest=idem_digest,
                    content_fingerprint=content_fingerprint,
                )
            
            await self.redis.set(
                idem_key,
                json.dumps({
                    "quiz_request_id": quiz_request_id,
                    "status": "queued",
                }),
                ex=TTL_3_MINUTES,
            )

            return CreateQuizRequestResult(
                quiz_request_id=quiz_request_id,
                status="queued",
                is_cached=False,
                should_enqueue=True,
                idem_digest=idem_digest,
                content_fingerprint=content_fingerprint,
            )
    
    async def create_quiz_request_v2(self, teacher_id: int, dto: QuizRequestCreate, supplied_idem_key, ) -> CreateQuizRequestResult:
        return await self.create_quiz_request(teacher_id, dto, supplied_idem_key)

    async def get_quiz_request_v2(self, quiz_request_id: int, teacher_id: int, classroom_id:int):
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException("Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")
        return await self.repo.get_quiz_request(quiz_request_id)

    async def delete_quiz(self, teacher_id: int, quiz_request_id: int, classroom_id: int):
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


        await self.db.commit()
        keys_to_delete = [
            QuizRedisKeys.result(quiz_request_id),
            QuizRedisKeys.stream(quiz_request_id),
        ]
        await self.redis.delete(*keys_to_delete)
        return True

    async def update_quiz_settings(
        self,
        teacher_id: int,
        classroom_id: int,
        quiz_request_id: int,
        dto: QuizRequestUpdate,
    ) -> QuizEditResponse:
        """
        Validates teacher authorization, merges partial updates with existing DB schedule 
        to guarantee schedule validity, updates DB record, and returns full details.
        """
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException("Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")

        existing_quiz = await self.repo.get_quiz_request(quiz_request_id)
        if not existing_quiz:
            raise NotFoundException("Quiz request tidak ditemukan.")

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

        await self.repo.update_quiz_request_settings(
            quiz_request_id=quiz_request_id,
            title=dto.title,
            max_retry=dto.max_retry,
            max_duration_minutes=dto.max_duration_minutes,
            start_time=dto.start_time,
            end_time=dto.end_time,
        )
        await self.db.commit()

        quiz =  await self.get_quiz_teacher(
            QuizRequestDetailQuery(classroom_id=classroom_id),
            teacher_id=teacher_id,
            id=quiz_request_id,
        )
        return QuizEditResponse(
            title=quiz.title,
            start_time=quiz.start_time,
            end_time= quiz.end_time,
            max_retry=quiz.max_retry,
            max_duration_minutes=quiz.max_duration_minutes,
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
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException("Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")

        if status == QuizRequestStatus.DRAFT and await self.repo.has_quiz_progress(quiz_request_id):
            raise BadRequestException("Kuis sudah dikerjakan siswa; tidak dapat dikembalikan ke draft.")
        if status == QuizRequestStatus.PUBLISH:
            quiz = await self.repo.get_quiz_request(quiz_request_id)
            if quiz is None or quiz.status != "done":
                raise BadRequestException("Kuis belum selesai dibuat atau gagal dibuat, belum bisa dipublikasikan.")

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
        return True

    async def get_quizzes_teacher(self, query: QuizRequestQuery, teacher_id: int) -> list[QuizRequestTeacherResponse]:
        quizzes = await self.repo.get_quizzes_teacher(query.classroom_id, teacher_id, query.status)
        return [QuizRequestTeacherResponse.model_validate(q) for q in quizzes]

    async def get_quiz_teacher(self, query: QuizRequestDetailQuery, teacher_id: int, id: int) -> QuizRequestTeacherDetailResponse:
        quiz = await self.repo.get_quiz_teacher(query.classroom_id, teacher_id, id)
        if not quiz:
            raise NotFoundException("Quiz tidak ditemukan")
        return QuizRequestTeacherDetailResponse.model_validate(quiz)

    async def get_students(self, query: QuizRequestDetailQuery, quiz_request_id: int, teacher_id: int) -> list[StudentQuizResponse]:
        data = await self.repo.get_students(query.classroom_id, teacher_id, quiz_request_id)
        return [
            StudentQuizResponse(
                student_profile=ProfileResponse(
                    id=student.user.id,
                    email=student.user.email,
                    student=StudentResponse.model_validate(student)
                ),
                quiz=(QuizRequestStudentProgressResponse.model_validate(progress)
                if progress is not None
                else None
                ),
            )
            for student, progress in data
        ]

    async def get_tasks_student(self, dto: StudentTaskRequest, student_id: int) -> StudentTaskResponse:
        from app.domains.users.schemas.student_dashboard_request import StudentTaskStatus
        try:
            match dto.status:
                case StudentTaskStatus.ALL:
                    modules = await self.content_repo.get_all_modules_student(dto.classroom_id, student_id, StudentModuleStatus.NOT_DONE)
                    exams = await self.repo.get_quizzes_student(dto.classroom_id, student_id, QuizRequestStudentQueryStatus.NOT_DONE)

                case StudentTaskStatus.MODULE:
                    modules = await self.content_repo.get_all_modules_student(dto.classroom_id, student_id, StudentModuleStatus.NOT_DONE)
                    exams = []

                case StudentTaskStatus.EXAM:
                    modules = []
                    exams = await self.repo.get_quizzes_student(dto.classroom_id, student_id, QuizRequestStudentQueryStatus.NOT_DONE)

                case _:
                    raise ValueError(f"Status tidak valid: {dto.status}")

            await self.db.commit()
            return StudentTaskResponse(
                exams=exams,
                modules=modules
            )

        except Exception as e:
            raise e

def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

def _generate_quiz_request_keys(teacher_id: int, dto: QuizRequestCreate, supplied_idem_key: str | None, ) -> tuple[str, str]:
    chapter_dicts = [
        chapter.model_dump(mode="json")
        for chapter in dto.chapters
    ]

    request_payload = {
        "teacher_id": teacher_id,
        "classroom_id": dto.classroom_id,
        "module_id": dto.module_id,
        "title": dto.title,
        "chapters": chapter_dicts,
        "max_duration_minutes": dto.max_duration_minutes,
        "max_retry": dto.max_retry,
        "start_time": dto.start_time.isoformat(),
        "end_time": dto.end_time.isoformat(),
    }

    generated_key = _hash_payload(request_payload)

    # Frontend key takes priority.
    # If it is None, use the generated key.
    raw_idem_key = supplied_idem_key or generated_key

    # Scope the supplied key to the authenticated teacher.
    idem_digest = _hash_payload({
        "teacher_id": teacher_id,
        "key": raw_idem_key,
    })

    # Content identity is independent of the frontend key.
    content_fingerprint = _hash_payload(request_payload)

    return idem_digest, content_fingerprint



