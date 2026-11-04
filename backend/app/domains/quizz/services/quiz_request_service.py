import json
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.contents.repositories.interfaces.module_interface import ModuleRepositoryInterface
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.quizz.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizz.models.quiz_request import QuizRequest, QuizRequestStatus
from app.domains.quizz.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizz.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.domains.quizz.schemas.quiz_request_create import QuizRequestCreate
from app.domains.quizz.schemas.soal_create_request import SaveQuizRequestPayload, SoalCreateRequest, SoalDataCreateRequest, StimulusCreateRequest
from app.domains.quizz.schemas.quiz_request_update import QuizRequestUpdate
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQuery, QuizRequestStudentQueryStatus
from app.domains.quizz.schemas.quiz_request_student_response import QuizRequestStudentProgressResponse, QuizRequestStudentResponse
from app.domains.quizz.schemas.student_quiz_response import StudentQuizResponse
from app.domains.users.schemas.profile_response import ProfileResponse
from app.domains.users.schemas.student_response import StudentResponse
from app.domains.users.schemas.student_tasks_request import StudentTaskRequest
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.utils.idempotency import generate_idempotency_key

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

    async def create_quiz_request(self, teacher_id: int, dto: QuizRequestCreate) -> tuple[int, str, bool, str]:
        chapter_dicts = [c.model_dump() for c in dto.chapters]
        chapter_ids = [c.chapter_id for c in dto.chapters]

        idem_key = generate_idempotency_key(
            teacher_id, dto.classroom_id, dto.module_id, dto.title, chapter_dicts, dto.max_duration_minutes, dto.max_retry,
            dto.start_time.isoformat(),
            dto.end_time.isoformat(),
        )

        is_valid, err_msg = await self.repo.validate_ownership_and_hierarchy(
            teacher_id, dto.classroom_id, dto.module_id, chapter_ids
        )

        if not is_valid:
            raise BadRequestException(err_msg)

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
            await self.repo.bulk_link_chapters(quiz_request_id, dto.chapters)
            await self.repo.db.commit()
        except Exception as e:
            await self.repo.db.rollback()
            raise e

        cached_content = await self.redis.get(f"quiz_content_cache:{idem_key}")

        if cached_content:
            parsed_questions = json.loads(cached_content)
            items_to_save = self._build_soal_requests(parsed_questions)

            await self.repo.save_quiz_data(
                quiz_request_id=quiz_request_id,
                classroom_id=dto.classroom_id,
                status_val="done",
                items=items_to_save,
            )

            result_key = f"quiz_result:{quiz_request_id}"
            await self.redis.set(result_key, json.dumps(parsed_questions), ex=TTL_3_MINUTES)

            return quiz_request_id, "done", True, idem_key

        job_meta = {"quiz_request_id": quiz_request_id, "status": "queued"}
        await self.redis.set(idem_key, json.dumps(job_meta), ex=TTL_3_MINUTES)

        return quiz_request_id, "queued", False, idem_key

    async def delete_quiz(self, teacher_id: int, quiz_request_id: int, classroom_id: int):
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

    async def update_quiz_settings(
        self,
        teacher_id: int,
        classroom_id: int,
        quiz_request_id: int,
        dto: QuizRequestUpdate,
    ) -> QuizRequestTeacherDetailResponse:
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
            max_duration_minutes=dto.max_duration_minutes,
            start_time=dto.start_time,
            end_time=dto.end_time,
        )
        await self.repo.db.commit()

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
        is_valid = await self.repo.validate_quiz_request(
            quiz_request_id=quiz_request_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
        )
        if not is_valid:
            raise ForbiddenException("Kelas atau Quiz Request tidak ditemukan atau Anda tidak memiliki akses.")

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
