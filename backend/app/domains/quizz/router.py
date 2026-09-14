from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, Query, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.exceptions import BadRequestException
from app.core.response import Response, get_response_message, COMMON_VALIDATION_RESPONSES
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.utils.role import Role
from app.domains.quizz.depedencies import get_quiz_service
from app.domains.quizz.models import Soal
from app.domains.quizz.schemas import (
    QuizRequestCreate,
    QuizRequestCreateResponse,
    QuizRequestStatus,
    SoalEditRequest,
    SoalOpsiResponse,
    SoalRegenerateRequest,
    SoalResponse,
    SoalStatusResponse,
)
from app.domains.quizz.services import QuizService
from app.tasks.quiz_tasks import TTL_3_MINUTES, process_quiz_request_task
from app.domains.quizz.schemas.quiz_request_query import QuizRequestDetailQuery, QuizRequestQuery
from app.domains.quizz.models.quiz_request import QuizRequest
from app.domains.quizz.schemas.quiz_request_teacher_response import QuizRequestTeacherDetailResponse, QuizRequestTeacherResponse
from app.core.redis import get_redis_client
from app.domains.quizz.schemas.soal_create_request import SaveQuizRequestPayload
from app.domains.quizz.schemas.soal_regenerate import RegenerateClusterRequest
from app.domains.quizz.schemas.quiz_delete_request import QuizDeleteRequest
from app.domains.quizz.schemas.quiz_request_update import QuizRequestUpdate
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQuery
from app.domains.quizz.schemas.quiz_request_student_response import QuizRequestStudentResponse


def _to_soal_response(soal: Soal) -> SoalResponse:
    return SoalResponse(
        id=soal.id,
        chapter_id=soal.chapter_id,
        stimulus_id=soal.stimulus_id,
        bloom_level=soal.bloom_level,
        question_text=soal.question_text,
        options=[SoalOpsiResponse(label=o.label, opsi_text=o.opsi_text) for o in sorted(soal.opsi, key=lambda o: o.label)],
        correct_option=soal.correct_option,
        langkah=[l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        kesimpulan=soal.kesimpulan,
        stimulus_text=soal.stimulus.readable_text if soal.stimulus else None,
        review_status=soal.review_status,
        review_priority=soal.review_priority,
        validation_notes=soal.validation_notes,
    )
# ==========================================
# SOAL ROUTER
# ==========================================
router_soal = APIRouter(prefix="/soal", tags=["soal"], route_class=WrappedRoute)

# @router_soal.post(
#     "/{soal_id}/approve",
#     description="Requires the TEACHER role.",
#     response_model=Response[SoalStatusResponse],
#     status_code=status.HTTP_200_OK,
# )
# async def approve_soal(
#     _: Roles(Role.TEACHER),
#     soal_id: Annotated[int, FastAPIPath()],
#     service: QuizService = Depends(get_quiz_service),
# ):
#     soal = await service.set_review_status(soal_id, "approved")
#     return Response(message=get_response_message(), data={"id": soal.id, "review_status": soal.review_status})


# @router_soal.post(
#     "/{soal_id}/reject",
#     description="Requires the TEACHER role.",
#     response_model=Response[SoalStatusResponse],
#     status_code=status.HTTP_200_OK,
# )
# async def reject_soal(
#     _: Roles(Role.TEACHER),
#     soal_id: Annotated[int, FastAPIPath()],
#     service: QuizService = Depends(get_quiz_service),
# ):
#     soal = await service.set_review_status(soal_id, "rejected")
#     return Response(message=get_response_message(), data={"id": soal.id, "review_status": soal.review_status})

# ==========================================
# Teacher ROUTER
# ==========================================
router_teacher_quizz = APIRouter(prefix="/teachers", tags=["teachers"], route_class=WrappedRoute)

@router_teacher_quizz.get(
    "/quizzes",
    description="Requires the TEACHER role.",
    response_model=Response[list[QuizRequestTeacherResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_list_quizzes(
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestQuery, Query()],
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.get_quizzes_teacher(query, teacher.profile_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result
    )

@router_teacher_quizz.get(
    "/quizzes/{quiz_id}",
    description="Requires the TEACHER role.",
    response_model=Response[QuizRequestTeacherDetailResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_quizz(
    quiz_id:int,
    teacher: Roles(Role.TEACHER),
    query: Annotated[QuizRequestDetailQuery, Query()],
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.get_quiz_teacher(query, teacher.profile_id, quiz_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result
    )

@router_teacher_quizz.post(
    "/quizzes",
    response_model=Response[QuizRequestCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz request and stream real-time progress",
    description="Requires TEACHER role. Upserts the quiz request, enqueues background worker if not cached, and returns a real-time SSE stream.",
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
    service: QuizService = Depends(get_quiz_service)
):
    """Upsert quiz request and immediately return an SSE progress stream."""
    quiz_request_id, job_status, is_cached, idem_key = await service.create_quiz_request(teacher.profile_id, query)

    if not is_cached:
        await process_quiz_request_task.kiq(quiz_request_id=quiz_request_id, idem_key=idem_key)

    async def event_generator():
        result_key = f"quiz_result:{quiz_request_id}"
        channel_key = f"quiz_stream:{quiz_request_id}"

        cached_result = await redis.get(result_key)
        if cached_result:
            await redis.expire(result_key, TTL_3_MINUTES)
            parsed_data = json.loads(cached_result)
            payload_data = json.dumps(
                {
                    "quiz_request_id": quiz_request_id,
                    "status": "done",
                    "completed": len(parsed_data),
                    "total": len(parsed_data),
                    "message": "Semua soal selesai dibuat (Cache Hit)",
                    "data": parsed_data,
                }
            )
            yield f"data: {payload_data}\n\n"
            return

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_key)

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    parsed = json.loads(data)
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
    responses=COMMON_VALIDATION_RESPONSES
)
async def save_quiz_requets(
    quiz_id: Annotated[int, FastAPIPath(..., description="ID of the quiz request to finalize")],
    payload: Annotated[SaveQuizRequestPayload, Body(...)],
    teacher: Roles(Role.TEACHER),
    service: QuizService = Depends(get_quiz_service),
):
    await service.update_publish_status(
        teacher_id=teacher.profile_id,
        classroom_id=payload.classroom_id,
        quiz_request_id=quiz_id,
        status=payload.status
    )

    return Response(
        message=f"Quiz request berhasil disimpan dengan status {payload.status.value.upper()}",
        data=True,
    )

@router_teacher_quizz.post(
    "/soal/stimulus/regenerate/{soal_id}",
    description="Requires the TEACHER role. Hanya berlaku untuk soal HOTS (stimulus_id terisi) -- meregenerasi seluruh cluster.",
    response_model=Response[list[SoalResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def regenerate_stimulus_soal(
    _: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[SoalRegenerateRequest, Body()],
    service: QuizService = Depends(get_quiz_service),
):
    soal = await service.get_soal(soal_id)
    if soal.stimulus_id is None:
        from app.core.exceptions import BadRequestException
        raise BadRequestException("soal ini tidak punya stimulus, edit langsung lewat PATCH /soal/{id}")

    updated = await service.regenerate_cluster(soal.stimulus_id, payload.feedback)
    return Response(message=get_response_message(), data=[_to_soal_response(s) for s in updated])

@router_teacher_quizz.patch(
    "/soal/{soal_id}",
    description="Requires the TEACHER role. Hanya berlaku untuk soal berdiri sendiri (stimulus_id kosong, biasanya LOTS).",
    response_model=Response[SoalResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def edit_soal(
    _: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[SoalEditRequest, Body()],
    service: QuizService = Depends(get_quiz_service),
):
    soal = await service.edit_soal(soal_id, payload)
    return Response(message=get_response_message(), data=_to_soal_response(soal))

@router_teacher_quizz.patch(
    "/quizzes/{quiz_id}",
    description="Requires the TEACHER role",
    response_model=Response[QuizRequestTeacherDetailResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def update_quiz(
    teacher: Roles(Role.TEACHER),
    quiz_id: Annotated[int, FastAPIPath()],
    payload: Annotated[QuizRequestUpdate, Body()],
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.update_quiz_settings(teacher.profile_id, payload.classroom_id, quiz_id, payload)
    return Response(message="Berhasil update quizz", data=result)

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
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.delete_quiz(teacher.profile_id, quiz_id, payload.classroom_id)
    return Response(message="Berhasil hapus quizz", data=result)

# ==========================================
# Student ROUTER
# ==========================================

router_student_quizz = APIRouter(prefix="/students", tags=["students"], route_class=WrappedRoute)
@router_student_quizz.get(
    "/quizzes",
    description="Requires the STUDENT role.",
    response_model=Response[list[QuizRequestStudentResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_list_quizzes(
    student: Roles(Role.STUDENT),
    query: Annotated[QuizRequestStudentQuery, Query()],
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.get_quizzes_student(query, student.profile_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result
    )


