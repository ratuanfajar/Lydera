from fastapi import APIRouter, Depends, status, Body
from app.core.security import CurrentUser
from app.core.route import WrappedRoute
from typing import Annotated
from app.domains.users.depedencies import get_user_service, get_teacher_service, get_student_service
from app.domains.users.services import UserService, TeacherService, StudentService
from app.core.response import COMMON_AUTH_RESPONSES, COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.domains.users.schemas import Login, TeacherCreate, StudentCreate, TeacherResponse, StudentResponse, ProfileResponse

router_user = APIRouter(prefix="/users", tags=["users"], route_class=WrappedRoute)

@router_user.post(
    "/login",
    response_model=Response[str],
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Email or password is invalid",
        },
    }
)
async def login(
     dto: Annotated[Login, Body()], 
     service: UserService = Depends(get_user_service)):
    token = await service.login(dto)
    return Response(
        message=get_response_message(),
        data=token
    )

@router_user.get(
    "/profile",
    response_model=Response[ProfileResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_AUTH_RESPONSES
)
async def profile(
     current_user: CurrentUser,
     service: UserService = Depends(get_user_service)):
    user_id = int(current_user.sub)
    profile = await service.get_profile(user_id)
    return Response(
        message=get_response_message(),
        data=profile
    )


router_teacher = APIRouter(prefix="/teachers", tags=["teachers"], route_class=WrappedRoute)

@router_teacher.post(
    "",
    response_model=Response[TeacherResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def register_teacher(
     dto: Annotated[TeacherCreate, Body()], 
     service: TeacherService = Depends(get_teacher_service)):
    teacher = await service.create_teacher(dto)
    return Response(
        message=get_response_message(),
        data=teacher
    )

router_student = APIRouter(prefix="/students", tags=["students"], route_class=WrappedRoute)

@router_student.post(
    "",
    response_model=Response[StudentResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def register_student(
     dto: Annotated[StudentCreate, Body()], 
     service: StudentService = Depends(get_student_service)):
    student = await service.create_student(dto)
    return Response(
        message=get_response_message(),
        data=student
    )