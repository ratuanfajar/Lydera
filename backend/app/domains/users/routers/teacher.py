from typing import Annotated

from fastapi import APIRouter, Body, Depends, status

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.users.dependencies import get_teacher_service
from app.domains.users.schemas import TeacherCreate, TeacherResponse
from app.domains.users.schemas.teacher_dashboard_request import TeacherDashboardRequest
from app.domains.users.schemas.teacher_dashboard_response import TeacherDashboardResponse
from app.domains.users.services import TeacherService
from app.utils.role import Role

router_teacher = APIRouter(prefix="/teachers", tags=["teachers"], route_class=WrappedRoute)


@router_teacher.post(
    "",
    response_model=Response[TeacherResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def register_teacher(
    dto: Annotated[TeacherCreate, Body()],
    service: TeacherService = Depends(get_teacher_service),
):
    teacher = await service.create_teacher(dto)
    return Response(
        message=get_response_message(),
        data=teacher,
    )


@router_teacher.get(
    "/dashboard",
    response_model=Response[TeacherDashboardResponse],
    description="Requires the Teacher role.",
)
async def get_teacher_dashboard(
    query: Annotated[TeacherDashboardRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    service: TeacherService = Depends(get_teacher_service),
):
    result = await service.dashboard_teacher(
        query,
        teacher_id=teacher.profile_id,
        user_id=int(teacher.sub),
    )
    return Response(
        message="Berhasil mendapatkan dashboard",
        data=result,
    )
