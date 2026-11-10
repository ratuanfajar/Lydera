import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Path as FastAPIPath, Query, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.redis import get_redis_client
from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.quizzer.depedencies import get_quiz_service, get_soal_service
from app.domains.quizzer.models import Soal
from app.domains.quizzer.schemas import (
    QuizRequestCreate,
    QuizRequestCreateResponse,
    QuizResultItem,
    SoalEditRequest,
    SoalOpsiResponse,
    SoalRegenerateRequest,
    SoalResponse,
)
from app.domains.quizzer.schemas.quiz_delete_request import QuizDeleteRequest
from app.domains.quizzer.schemas.quiz_request_query import (
    QuizRequestDetailQuery,
    QuizRequestQuery,
    QuizRequestStudentDetailQuery,
)
from app.domains.quizzer.schemas.quiz_request_teacher_response import (
    QuestionStimulusResponse,
    QuizRequestTeacherDetailResponse,
    QuizRequestTeacherResponse,
)
from app.domains.quizzer.schemas.soal_create_request import SaveQuizRequestPayload
from app.domains.quizzer.schemas.student_quiz_response import StudentQuizResponse
from app.domains.quizzer.services.quiz_request_service import QuizRequestService
from app.domains.quizzer.services.soal_service import SoalService
from app.tasks.quiz_tasks import TTL_3_MINUTES, process_quiz_request_task
from app.utils.role import Role
from app.core.exceptions import BadRequestException, NotFoundException
from app.domains.quizzer.schemas.soal_edit_request import StimulusEditRequest
from app.core.redis_keys import QuizRedisKeys
from app.domains.quizzer.schemas.quiz_edit_response import QuizEditResponse
from app.domains.quizzer.schemas.quiz_request_update import QuizRequestUpdate

router_teacher_quizz_v2 = APIRouter(
    prefix="/v2/teachers",
    tags=["teachers-v2"],
    route_class=WrappedRoute,
)


def _to_soal_response(soal: Soal) -> SoalResponse:
    return SoalResponse(
        id=soal.id,
        chapter_id=soal.chapter_id,
        stimulus_id=soal.stimulus_id,
        bloom_level=soal.bloom_level,
        question_text=soal.question_text,
        options=[
            SoalOpsiResponse(label=o.label, opsi_text=o.opsi_text)
            for o in sorted(soal.opsi, key=lambda o: o.label)
        ],
        correct_option=soal.correct_option,
        langkah=[l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        kesimpulan=soal.kesimpulan,
        stimulus_text = soal.stimulus.readable_text if soal.stimulus else None,
        stimulus =  QuestionStimulusResponse.model_validate(soal.stimulus) if soal.stimulus else None,
        review_status=soal.review_status,
        review_priority=soal.review_priority,
        validation_notes=soal.validation_notes,
    )


@router_teacher_quizz_v2.post(
    "/quizzes",
    response_model=Response[QuizRequestCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz request",
    description=(
        "Requires TEACHER role. Creates a quiz request and enqueues "
        "the background worker if the content is not cached."
    ),
    responses=COMMON_VALIDATION_RESPONSES,
)
async def create_quiz_request_v2(
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestCreate, Body()],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.create_quiz_request_v2(
        teacher_id=teacher.profile_id,
        dto=query,
        supplied_idem_key=idempotency_key,
    )

    if result.should_enqueue:
        await process_quiz_request_task.kiq(
            quiz_request_id=result.quiz_request_id,
            idem_key=result.idem_digest,
            content_fingerprint=result.content_fingerprint,
        )

    return Response(
        message=f"Quiz request berhasil dibuat",
        data=QuizRequestCreateResponse(
            idem_key= result.idem_digest,
            is_cached= result.is_cached,
            quiz_request_id= result.quiz_request_id,
            status=result.status
        ),
    )

@router_teacher_quizz_v2.get(
    "/quizzes/{quiz_request_id}/stream",
    summary="Stream quiz generation progress",
    description=(
        "Requires TEACHER role. Streams progress for an existing quiz request "
        "using Server-Sent Events (SSE). Does not create a quiz."
    ),
    responses={
        200: {
            "description": "Server-Sent Events progress stream",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'data: {"quiz_request_id": 12, "status": "running", '
                            '"completed": 1, "total": 4, '
                            '"message": "Soal 1/4 selesai diproses"}\n\n'
                            'data: {"quiz_request_id": 12, "status": "done", '
                            '"completed": 4, "total": 4, '
                            '"message": "Semua soal selesai dibuat", "data": [...]}\n\n'
                        ),
                    }
                }
            },
        },
        **COMMON_VALIDATION_RESPONSES,
    },
)
async def stream_quiz_request_v2(
    quiz_request_id: int,
    teacher: Roles(Role.TEACHER),
    redis: Annotated[Redis, Depends(get_redis_client)],
    classroom_id: Annotated[int, Query()],
    service: QuizRequestService = Depends(get_quiz_service),
):
    quiz_request = await service.get_quiz_request_v2(
        quiz_request_id,
        teacher.profile_id,
        classroom_id
    )

    if quiz_request is None:
        raise NotFoundException("Quiz request tidak ditemukan.")

    progress_key = QuizRedisKeys.progress(quiz_request_id)
    result_key = QuizRedisKeys.result(quiz_request_id)
    channel_key = QuizRedisKeys.stream(quiz_request_id)

    async def event_generator():

        def decode_payload(raw_data):
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            if isinstance(raw_data, str):
                return json.loads(raw_data)

            return raw_data

        try:
            if quiz_request.status == "done":
                final_result = await redis.get(result_key)

                if final_result:
                    payload = decode_payload(final_result)
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                # Fallback: check the last progress snapshot.
                progress_data = await redis.get(progress_key)

                if progress_data:
                    payload = decode_payload(progress_data)
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

                # Both Redis keys may have expired.
                yield f"data: {json.dumps({
                    'quiz_request_id': quiz_request_id,
                    'status': 'done',
                    'message': 'Quiz sudah selesai, tetapi data hasil di Redis sudah kedaluwarsa.',
                })}\n\n"
                return

            if quiz_request.status == "failed":
                final_result = await redis.get(result_key)

                if final_result:
                    payload = decode_payload(final_result)
                else:
                    progress_data = await redis.get(progress_key)

                    if progress_data:
                        payload = decode_payload(progress_data)
                    else:
                        payload = {
                            "quiz_request_id": quiz_request_id,
                            "status": "failed",
                            "message": "Pembuatan kuis gagal.",
                        }

                yield f"data: {json.dumps(payload)}\n\n"
                return

            pubsub = redis.pubsub()
            last_seq = -1

            try:
                # Subscribe before reading the snapshot.
                # This prevents missing events published between
                # reading the snapshot and subscribing.
                await pubsub.subscribe(channel_key)

                cached_event = await redis.get(progress_key)

                if cached_event:
                    payload = decode_payload(cached_event)
                    last_seq = payload.get("seq", -1)

                    yield f"data: {json.dumps(payload)}\n\n"

                    if payload.get("status") in ("done", "failed"):
                        return

                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )

                    if message and message["type"] == "message":
                        payload = decode_payload(message["data"])

                        seq = payload.get("seq", -1)

                        if seq <= last_seq:
                            continue

                        last_seq = seq

                        yield f"data: {json.dumps(payload)}\n\n"

                        if payload.get("status") in ("done", "failed"):
                            break

                    # Keep the SSE connection alive.
                    yield ": ping\n\n"

            finally:
                await pubsub.unsubscribe(channel_key)
                await pubsub.close()

        except asyncio.CancelledError:
            # Client disconnected.
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
