from fastapi import APIRouter, Depends, Path, status, Body
from app.core.security import CurrentUser, Roles
from app.core.route import WrappedRoute
from typing import Annotated
from app.domains.users.depedencies import get_user_service, get_teacher_service, get_student_service
from app.domains.users.services import UserService, TeacherService, StudentService
from app.domains.classrooms.services import ClassroomService
from app.domains.classrooms.depedencies import get_classroom_service
from app.core.response import COMMON_AUTH_RESPONSES, COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.domains.users.schemas import Login, TeacherCreate, StudentCreate, TeacherResponse, StudentResponse, ProfileResponse, StudentDashboardResponse, StudentDashboardRequest
from app.utils.role import Role
from app.domains.users.schemas.student_tasks_request import StudentTaskRequest
from app.domains.users.schemas.student_tasks_response import StudentTaskResponse
from app.domains.contents.schemas.module.student_module_request import StudentModuleRequest
from app.domains.contents.schemas.module.student_module_response import StudentModuleResponse
from app.domains.contents.schemas.module.student_module_detail_request import StudentModuleDetailRequest
from app.domains.contents.schemas.chapters.student_chapter_detail_response import StudentChapterDetailResponse
from app.domains.users.schemas.taecher_dashboard_request import TeacherDashboardRequest
from app.domains.users.schemas.taecher_dashboard_response import TeacherDashboardResponse
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleRequest
from app.domains.contents.schemas.module.teacher_module_response import TeacherModuleResponse

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


@router_teacher.get(
    "/dashboard",
    response_model=Response[TeacherDashboardResponse],
    description="Requires the STUDENT role.",
)
async def get_teacher_dashboard(
    query: Annotated[TeacherDashboardRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    service: TeacherService = Depends(get_teacher_service),
):
    result = await service.dashboard_teacher(
        query,
        teacher_id=teacher.profile_id,
        user_id=int(teacher.sub)
    )
    return Response(
        message="Berhasil mendapatkan dashboard",
        data=result
    )

@router_teacher.get(
    "/modules",
    response_model=Response[list[TeacherModuleResponse]],
    description="Requires the Teacher role.",
)
async def get_all_modules_teacher(
    query: Annotated[TeacherModuleRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    service: TeacherService = Depends(get_teacher_service),
):    
    result = await service.get_teacher_modules(
        query,
        teacher_id=teacher.profile_id
    )
    return Response(
        message="Berhasil mendapatkan data modules",
        data=result
    )

# Student
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
    # Akses classroom_id via query.classroom_id
    
    result = await service.dashboard_student(
        query,
        student_id=student.profile_id,
        user_id=int(student.sub)
    )
    return Response(
        message="Berhasil mendapatkan dashboard",
        data=result
    )

@router_student.get(
    "/dashboard/tasks",
    response_model=Response[StudentTaskResponse],
    description="Requires the STUDENT role.",
)
async def get_student_dashboard_task(
    query: Annotated[StudentTaskRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):    
    result = await service.get_tasks_student(
        query,
        student_id=student.profile_id
    )
    return Response(
        message="Berhasil mendapatkan data tasks",
        data=result
    )

@router_student.get(
    "/modules",
    response_model=Response[list[StudentModuleResponse]],
    description="Requires the STUDENT role.",
)
async def get_all_modules_student(
    query: Annotated[StudentModuleRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):    
    result = await service.get_student_modules(
        query,
        student_id=student.profile_id
    )
    return Response(
        message="Berhasil mendapatkan data tasks",
        data=result
    )

@router_student.get(
    "/modules/{module_id}",
    response_model=Response[StudentModuleResponse],
    description="Requires the STUDENT role.",
)
async def get_detail_module_student(
    module_id: Annotated[int, Path()],
    query: Annotated[StudentModuleDetailRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):    
    result = await service.get_student_module(
        query,
        student_id=student.profile_id,
        module_id=module_id
    )
    return Response(
        message="Berhasil mendapatkan data module",
        data=result
    )

@router_student.post(
    "/chapters/{chapter_id}/start",
    response_model=Response[StudentChapterDetailResponse],
    description="Requires the STUDENT role.",
)
async def get_detail_chapter_student(
    chapter_id: Annotated[int, Path()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):    
    result = await service.start_chapter(
        student_id=student.profile_id,
        chapter_id=chapter_id
    )
    return Response(
        message="Berhasil mendapatkan data detail chapter",
        data=result
    )

@router_student.post(
    "/chapters/{chapter_id}/mark-complete",
    response_model=Response[StudentModuleResponse],
    description="Requires the STUDENT role.",
)
async def mark_chapter(
    chapter_id: Annotated[int, Path()],
    student: Roles(Role.STUDENT),
    service: StudentService = Depends(get_student_service),
):    
    result = await service.mark_chapter_as_completed(
        student_id=student.profile_id,
        chapter_id=chapter_id
    )
    return Response(
        message="Selamat telah menyelesaikan chapter",
        data=result
    )

# @router_student.get(
#     "/modules/{module_id}",
#     response_model=Response[StudentModuleResponse],
#     description="Requires the STUDENT role.",
# )
# async def get_detail_module_student(
#     module_id: Annotated[int, Path()],
#     query: Annotated[StudentModuleDetailRequest, Depends()],
#     student: Roles(Role.STUDENT),
#     service: StudentService = Depends(get_student_service),
# ):    
#     result = await service.get_student_module(
#         query,
#         student_id=student.profile_id,
#         module_id=module_id
#     )
#     return Response(
#         message="Berhasil mendapatkan data tasks",
#         data=result
#     )




