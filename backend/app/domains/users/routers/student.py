from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.users.dependencies import get_student_service
from app.domains.users.schemas import StudentCreate, StudentResponse
from app.domains.users.schemas.student_dashboard_request import StudentDashboardRequest
from app.domains.users.schemas.student_dashboard_response import StudentDashboardResponse
from app.domains.users.services import StudentService
from app.utils.role import Role

router_student = APIRouter(prefix="/students", tags=["students"], route_class=WrappedRoute)


@router_student.post(
    "",
    response_model=Response[StudentResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def register_student(
    dto: Annotated[StudentCreate, Body()],
    service: StudentService = Depends(get_student_service),
):
    student = await service.create_student(dto)
    return Response(
        message=get_response_message(),
        data=student,
    )


@router_student.get(
    "/dashboard",
    response_model=Response[StudentDashboardResponse],
    description="Requires the STUDENT role.",
)
async def get_student_dashboard(
    query: Annotated[StudentDashboardRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):
    result = await service.dashboard_student(
        query,
        student_id=student.profile_id,
        user_id=int(student.sub),
    )
    return Response(
        message="Berhasil mendapatkan dashboard",
        data=result,
    )
