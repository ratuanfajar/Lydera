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
from app.core.exceptions import BadRequestException
from app.domains.quizzer.schemas.soal_edit_request import StimulusEditRequest
from app.core.redis_keys import QuizRedisKeys

router_teacher_quizz = APIRouter(
    prefix="/teachers",
    tags=["teachers"],
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


@router_teacher_quizz.get(
    "/quizzes",
    description="Requires the TEACHER role.",
    response_model=Response[list[QuizRequestTeacherResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_list_quizzes(
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestQuery, Query()],
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.get_quizzes_teacher(query, teacher.profile_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result,
    )


@router_teacher_quizz.get(
    "/quizzes/{quiz_id}",
    description="Requires the TEACHER role.",
    response_model=Response[QuizRequestTeacherDetailResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_quizz(
    quiz_id: int,
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestDetailQuery, Query()],
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.get_quiz_teacher(query, teacher.profile_id, quiz_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result,
    )


@router_teacher_quizz.post(
    "/quizzes",
    response_model=Response[QuizRequestCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz request and stream real-time progress",
    description=(
        "Requires TEACHER role. Upserts the quiz request, enqueues background worker "
        "if not cached, and returns a real-time SSE stream."
        "its have idempotency key in header as Idempotency-Key"
    ),
    responses={
        200: {
            "description": "Server-Sent Events (SSE) real-time event stream",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'data: {"quiz_request_id": 12, "status": "running", "completed": 0, "total": 4, "message": "Memulai pembuatan 4 soal..."}\n\n'
                            'data: {"quiz_request_id": 12, "status": "running", "completed": 1, "total": 4, "message": "Soal 1/4 selesai diproses"}\n\n'
                            'data: {"quiz_request_id": 12, "status": "done", "completed": 4, "total": 4, "message": "Semua soal selesai dibuat", "data": [...]}\n\n'
                        ),
                    }
                }
            },
        },
        **COMMON_VALIDATION_RESPONSES,
    },
)
async def create_quiz_request(
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestCreate, Body()],
    redis: Annotated[Redis, Depends(get_redis_client)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
    service: QuizRequestService = Depends(get_quiz_service),
):
    """Upsert quiz request and immediately return an SSE progress stream."""
    result = await service.create_quiz_request(
        teacher_id=teacher.profile_id,
        dto=query,
        supplied_idem_key=idempotency_key,
    )

    quiz_request_id = result.quiz_request_id
    # --------------------------------------------------
    # 1. Enqueue only when a new request needs generation
    # --------------------------------------------------
    if result.should_enqueue:
        await process_quiz_request_task.kiq(
            quiz_request_id=quiz_request_id,
            idem_key=result.idem_digest,
            content_fingerprint=result.content_fingerprint,
        )

    # --------------------------------------------------
    # 3. SSE stream
    # --------------------------------------------------
    async def event_generator():
        progress_key = QuizRedisKeys.progress(quiz_request_id)
        result_key = QuizRedisKeys.result(quiz_request_id)
        channel_key = QuizRedisKeys.stream(quiz_request_id)

        pubsub = redis.pubsub()
        last_seq = -1

        try:
            await pubsub.subscribe(channel_key)
            cached_event = await redis.get(progress_key)

            if not cached_event:
                cached_event = await redis.get(progress_key)

            if cached_event:
                if isinstance(cached_event, bytes):
                    cached_event = cached_event.decode("utf-8")

                parsed = json.loads(cached_event)
                last_seq = parsed.get("seq", -1)

                yield f"data: {cached_event}\n\n"

                if parsed.get("status") in ("done", "failed"):
                    return
            
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                if message and message["type"] == "message":
                    data = message["data"]

                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    parsed = json.loads(data)
                    seq = parsed.get("seq", -1)
                    
                    if seq <= last_seq:
                        continue

                    last_seq = seq

                    yield f"data: {data}\n\n"

                    if parsed.get("status") in ("done", "failed"):
                        break

                yield ": ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_key)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router_teacher_quizz.patch(
    "/quizzes/statuses/{quiz_id}",
    description="Requires the TEACHER role. change status quiz.",
    response_model=Response[bool],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def save_quiz_requets(
    quiz_id: Annotated[
        int,
        FastAPIPath(..., description="ID of the quiz request to finalize"),
    ],
    payload: Annotated[SaveQuizRequestPayload, Body(...)],
    teacher: Roles(Role.TEACHER),
    service: QuizRequestService = Depends(get_quiz_service),
):
    await service.update_publish_status(
        teacher_id=teacher.profile_id,
        classroom_id=payload.classroom_id,
        quiz_request_id=quiz_id,
        status=payload.status,
    )

    return Response(
        message=f"Quiz request berhasil disimpan dengan status {payload.status.value.upper()}",
        data=True,
    )


@router_teacher_quizz.post(
    "/soal/stimulus/regenerate/{soal_id}",
    description=(
        "Requires the TEACHER role. Hanya berlaku untuk soal HOTS "
        "(stimulus_id terisi) -- meregenerasi seluruh cluster."
    ),
    response_model=Response[list[SoalResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def regenerate_stimulus_soal(
    teacher: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[SoalRegenerateRequest, Body()],
    service: SoalService = Depends(get_soal_service),
):
    try:
        updated = await service.regenerate_cluster(soal_id, teacher.profile_id, payload.feedback)
        return Response(message=get_response_message(), data=[_to_soal_response(s) for s in updated])
    except ValueError as e:
        raise BadRequestException(str(e))

@router_teacher_quizz.patch(
    "/soal/{soal_id}",
    description="Requires the TEACHER role. Edit langsung soal, opsi, kunci, langkah, dan kesimpulan; berlaku untuk soal LOTS maupun HOTS. Hanya untuk kuis draft yang belum dikerjakan siswa; kuis publish atau yang sudah dikerjakan dibalas 400 (kunci terkunci).",
    response_model=Response[SoalResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def edit_soal(
    teacher: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[SoalEditRequest, Body()],
    service: SoalService = Depends(get_soal_service),
):
    soal = await service.edit_soal(soal_id, teacher.profile_id, payload)
    return Response(message=get_response_message(), data=_to_soal_response(soal))

@router_teacher_quizz.patch(
    "/soal/{soal_id}/stimulus",
    description=(
        "Requires the TEACHER role. Edit langsung stimulus pada bentuk aslinya: source_markup untuk stimulus teks, "
        "spesifikasi (dan narasi opsional) untuk stimulus bertipe. Bacaan diturunkan ulang dan seluruh soal di cluster diverifikasi ulang. Hanya untuk kuis draft yang belum dikerjakan siswa."
    ),
    response_model=Response[list[SoalResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def edit_stimulus(
    teacher: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[StimulusEditRequest, Body()],
    service: SoalService = Depends(get_soal_service),
):
    updated = await service.edit_stimulus(soal_id, teacher.profile_id, payload)
    return Response(message=get_response_message(), data=[_to_soal_response(s) for s in updated])

@router_teacher_quizz.delete(
    "/quizzes/{quiz_id}",
    description="Requires the TEACHER role",
    response_model=Response[bool],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def delete_quiz(
    teacher: Roles(Role.TEACHER),
    quiz_id: Annotated[int, FastAPIPath()],
    payload: Annotated[QuizDeleteRequest, Body()],
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.delete_quiz(teacher.profile_id, quiz_id, payload.classroom_id)
    return Response(message="Berhasil hapus quizz", data=result)

@router_teacher_quizz.get(
    "/quizzes/{quiz_id}/students",
    description="Requires the TEACHER role.",
    response_model=Response[list[StudentQuizResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_list_student_progress(
    quiz_id: Annotated[int, FastAPIPath()],
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestQuery, Query()],
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.get_students(query, quiz_id, teacher.profile_id)
    return Response(
        message="Berhasil dapatkan list progres quiz murid",
        data=result,
    )
