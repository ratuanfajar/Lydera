from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, Query, status
from fastapi.responses import StreamingResponse

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.quizz.depedencies import (
    get_quiz_result_service,
    get_quiz_service,
    get_quiz_taking_service,
)
from app.domains.quizz.schemas import QuizResultItem, SoalSubmitRequest, SoalSubmitResponse
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQuery
from app.domains.quizz.schemas.quiz_request_student_response import (
    QuestionStudentSteps,
    QuizRequestStudentResponse,
)
from app.domains.quizz.schemas.step_request import AddStepRequest
from app.domains.quizz.services.quiz_request_service import QuizRequestService
from app.domains.quizz.services.quiz_result_service import QuizResultService
from app.domains.quizz.services.quiz_taking_service import QuizTakingService
from app.domains.users.schemas.student_tasks_request import StudentTaskRequest
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.utils.role import Role

router_student_quizz = APIRouter(
    prefix="/students",
    tags=["students"],
    route_class=WrappedRoute,
)


@router_student_quizz.get(
    "/quizzes",
    description="Requires the STUDENT role.",
    response_model=Response[list[QuizRequestStudentResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_list_quizzes(
    student: Roles(Role.STUDENT),
    query: Annotated[QuizRequestStudentQuery, Query()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    result = await service.get_quizzes_student(query, student.profile_id)
    return Response(
        message="Berhasil dapatkan list quiz",
        data=result,
    )


@router_student_quizz.post(
    "/quizzes/{quiz_id}/start",
    description=(
        "Requires STUDENT role. Returns SSE stream starting with question list "
        "followed by countdown ticks."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": (
                "SSE Stream. Event 1 sends question list JSON; subsequent events "
                "send countdown ticks."
            ),
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": (
                            'data: {"type":"INIT","questions":[...],'
                            '"target_end_time":"..."}\n\ndata: '
                            '{"type":"TICK","time":"15:00"}\n\n'
                        ),
                    }
                }
            },
        },
        **COMMON_VALIDATION_RESPONSES,
    },
)
async def start_quiz(
    student: Roles(Role.STUDENT),
    quiz_id: Annotated[int, FastAPIPath()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    stream_gen = await service.initialize_and_stream_quiz(
        student_id=student.profile_id,
        quiz_id=quiz_id,
    )
    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router_student_quizz.post(
    "/quizzes/{quiz_id}/finish",
    description=(
        "Submits the quiz early, closes active SSE streams, and dispatches the "
        "review job queue."
    ),
    response_model=Response[dict],
    status_code=status.HTTP_200_OK,
)
async def finish_quiz(
    student: Roles(Role.STUDENT),
    quiz_id: Annotated[int, FastAPIPath()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    await service.finish_and_enqueue_review(
        quiz_id=quiz_id,
        student_id=student.profile_id,
    )
    return Response(
        message="Kuis berhasil dikumpulkan dan sedang dievaluasi.",
        data={"quiz_id": quiz_id, "status": "PROCESSING"},
    )


@router_student_quizz.get(
    "/quizzes/{quiz_request_id}/my-results",
    description=(
        "Requires the STUDENT role. Hasil kuis siswa yang login: untuk soal yang dijawab "
        "salah, justifikasi personal (perbandingan langkah pengerjaan siswa vs yang benar) "
        "dievaluasi di sini kalau belum pernah, lalu disimpan -- panggilan berikutnya "
        "pakai hasil tersimpan."
    ),
    response_model=Response[list[QuizResultItem]],
    status_code=status.HTTP_200_OK,
)
async def get_my_quiz_results(
    student: Roles(Role.STUDENT),
    quiz_request_id: Annotated[int, FastAPIPath()],
    service: QuizResultService = Depends(get_quiz_result_service),
):
    results = await service.get_quiz_results(quiz_request_id, student.profile_id)
    return Response(message=get_response_message(), data=results)


@router_student_quizz.post(
    "/soal/{soal_id}/select-option",
    description="Requires the STUDENT role. Simpan jawaban siswa untuk satu soal.",
    response_model=Response[SoalSubmitResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def submit_soal_answer(
    student: Roles(Role.STUDENT),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[SoalSubmitRequest, Body()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    await service.submit_answer(soal_id, student.profile_id, payload)
    return Response(
        message=get_response_message(),
        data={"soal_id": soal_id, "status": "saved"},
    )


@router_student_quizz.post(
    "/soal/{soal_id}/steps",
    description="Requires the STUDENT role. Simpan langkah pengerjaan siswa untuk satu soal.",
    response_model=Response[QuestionStudentSteps],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def submit_step_soal_answer(
    student: Roles(Role.STUDENT),
    soal_id: Annotated[int, FastAPIPath()],
    payload: Annotated[AddStepRequest, Body()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    result = await service.add_step(payload, soal_id, student.profile_id)
    return Response(message=get_response_message(), data=result)


@router_student_quizz.delete(
    "/steps/{step_id}",
    description="Requires the STUDENT role. Hapus langkah pengerjaan.",
    response_model=Response[bool],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def delete_step_soal_answer(
    student: Roles(Role.STUDENT),
    step_id: Annotated[int, FastAPIPath()],
    service: QuizTakingService = Depends(get_quiz_taking_service),
):
    result = await service.delete_step(step_id, student.profile_id)
    return Response(message="Berhasil hapus step", data=result)


@router_student_quizz.get(
    "/dashboard/tasks",
    response_model=Response[StudentTaskResponse],
    description="Requires the STUDENT role.",
)
async def get_student_dashboard_task(
    query: Annotated[StudentTaskRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: QuizRequestService = Depends(get_quiz_service),
):
    result = await service.get_tasks_student(
        query,
        student_id=student.profile_id,
    )
    return Response(
        message="Berhasil mendapatkan data tasks",
        data=result,
    )
