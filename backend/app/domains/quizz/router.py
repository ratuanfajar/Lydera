from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, status

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
from app.tasks.quiz_tasks import process_quiz_request_task


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
# QUIZ REQUEST ROUTER
# ==========================================
router_quiz_requests = APIRouter(prefix="/quiz-requests", tags=["quiz"], route_class=WrappedRoute)


@router_quiz_requests.post(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[QuizRequestCreateResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def create_quiz_request(
    _: Roles(Role.TEACHER),
    payload: Annotated[QuizRequestCreate, Body()],
    service: QuizService = Depends(get_quiz_service),
):
    quiz_request_id = await service.create_quiz_request(payload.module_id, payload.chapters)
    await process_quiz_request_task.kiq(quiz_request_id=quiz_request_id)
    return Response(
        message=get_response_message(),
        data={"quiz_request_id": quiz_request_id, "status": "queued"},
    )


@router_quiz_requests.get(
    "/{quiz_request_id}/status",
    response_model=Response[QuizRequestStatus],
    status_code=status.HTTP_200_OK,
)
async def get_quiz_request_status(
    quiz_request_id: Annotated[int, FastAPIPath()],
    service: QuizService = Depends(get_quiz_service),
):
    quiz_request = await service.get_quiz_request_status(quiz_request_id)
    return Response(
        message=get_response_message(),
        data={"quiz_request_id": quiz_request_id, "status": quiz_request.status, "error": quiz_request.error},
    )


@router_quiz_requests.get(
    "/{quiz_request_id}/soal",
    response_model=Response[list[SoalResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_soal_for_request(
    quiz_request_id: Annotated[int, FastAPIPath()],
    service: QuizService = Depends(get_quiz_service),
):
    soal_list = await service.list_soal_for_request(quiz_request_id)
    return Response(message=get_response_message(), data=[_to_soal_response(s) for s in soal_list])


# ==========================================
# SOAL ROUTER
# ==========================================
router_soal = APIRouter(prefix="/soal", tags=["soal"], route_class=WrappedRoute)


@router_soal.get(
    "/{soal_id}",
    response_model=Response[SoalResponse],
    status_code=status.HTTP_200_OK,
)
async def get_soal(
    soal_id: Annotated[int, FastAPIPath()],
    service: QuizService = Depends(get_quiz_service),
):
    soal = await service.get_soal(soal_id)
    return Response(message=get_response_message(), data=_to_soal_response(soal))


@router_soal.patch(
    "/{soal_id}",
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


@router_soal.post(
    "/{soal_id}/approve",
    description="Requires the TEACHER role.",
    response_model=Response[SoalStatusResponse],
    status_code=status.HTTP_200_OK,
)
async def approve_soal(
    _: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    service: QuizService = Depends(get_quiz_service),
):
    soal = await service.set_review_status(soal_id, "approved")
    return Response(message=get_response_message(), data={"id": soal.id, "review_status": soal.review_status})


@router_soal.post(
    "/{soal_id}/reject",
    description="Requires the TEACHER role.",
    response_model=Response[SoalStatusResponse],
    status_code=status.HTTP_200_OK,
)
async def reject_soal(
    _: Roles(Role.TEACHER),
    soal_id: Annotated[int, FastAPIPath()],
    service: QuizService = Depends(get_quiz_service),
):
    soal = await service.set_review_status(soal_id, "rejected")
    return Response(message=get_response_message(), data={"id": soal.id, "review_status": soal.review_status})


@router_soal.post(
    "/{soal_id}/regenerate",
    description="Requires the TEACHER role. Hanya berlaku untuk soal HOTS (stimulus_id terisi) -- meregenerasi seluruh cluster.",
    response_model=Response[list[SoalResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def regenerate_soal(
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
