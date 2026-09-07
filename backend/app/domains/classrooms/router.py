from fastapi import APIRouter, Depends, Path, status, Body
from app.utils.role import Role
from app.core.route import WrappedRoute
from typing import Annotated
from app.core.security import Roles
from app.domains.classrooms.depedencies import get_classroom_service, get_classroom_type_service
from app.domains.classrooms.services import ClassroomService, ClassroomTypeService
from app.core.response import Response, COMMON_VALIDATION_RESPONSES
from app.domains.classrooms.schemas import ClassroomResponse, ClassroomTypeResponse, ClassroomCreate
from typing import Annotated
from fastapi import APIRouter, Depends, Body, Path, status


router_classrooms = APIRouter(prefix="/classrooms", tags=["classrooms"], route_class=WrappedRoute)

@router_classrooms.post(
    "",
    description="Create a new classroom. Requires the TEACHER role.",
    response_model=Response[ClassroomResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def create_classroom(
     dto: Annotated[ClassroomCreate, Body()], 
     teacher: Roles(Role.TEACHER),
     service: ClassroomService = Depends(get_classroom_service)
):
    result = await service.create_classroom(dto, teacher.profile_id)
    return Response(
        data=result,
        message="Classroom created successfully"
    )

@router_classrooms.get(
    "",
    description="Get list of classrooms for the logged-in user. Requires TEACHER or STUDENT role.",
    response_model=Response[list[ClassroomResponse]],
    status_code=status.HTTP_200_OK
)
async def get_classrooms(
     current_user: Roles(Role.TEACHER, Role.STUDENT),
     service: ClassroomService = Depends(get_classroom_service)
):
    classrooms = await service.get_classrooms(current_user.profile_id, current_user.role)
    return Response(
        data=classrooms,
        message="Classrooms retrieved successfully"
    )

@router_classrooms.get(
    "/{classroom_id}",
    description="Get a classroom by ID. Requires TEACHER or STUDENT role.",
    response_model=Response[ClassroomResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_classroom(
     classroom_id: Annotated[int, Path(title="The ID of the classroom")],
     current_user: Roles(Role.TEACHER, Role.STUDENT),
     service: ClassroomService = Depends(get_classroom_service)
):
    classroom = await service.get_classroom_by_id(classroom_id, current_user.profile_id, current_user.role)
    return Response(
        data=classroom,
        message="Classroom retrieved successfully"
    )

@router_classrooms.post(
    "/join",
    description="Join a classroom using a code. Requires the STUDENT role.",
    response_model=Response[None],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def join_classroom(
     code: Annotated[str, Body(embed=True, description="The 7-character classroom code")], 
     student: Roles(Role.STUDENT),
     service: ClassroomService = Depends(get_classroom_service)
):
    await service.join_classroom(code, student.profile_id)
    return Response(
        data=True,
        message="Successfully joined the classroom"
    )


router_classrooms_types = APIRouter(prefix="/classroom-types", tags=["classroom-types"], route_class=WrappedRoute)

@router_classrooms_types.get(
    "",
    description="Get a list of all available classroom types. Publicly accessible.",
    response_model=Response[list[ClassroomTypeResponse]],
    status_code=status.HTTP_200_OK
)
async def get_list_classroom_types(
     service: ClassroomTypeService = Depends(get_classroom_type_service)
):
    types = await service.get_classroom_types()
    return Response(
        data=types,
        message="Classroom types retrieved successfully"
    )