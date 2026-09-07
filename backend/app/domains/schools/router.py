from fastapi import APIRouter, Depends, Path, status, Body
from app.utils.role import Role
from app.core.route import WrappedRoute
from typing import Annotated
from app.core.security import Roles
from app.domains.schools.depedencies import get_school_service
from app.domains.schools.services import SchoolService
from app.core.response import Response, COMMON_VALIDATION_RESPONSES, get_response_message
from app.domains.schools.schemas import SchoolResponse, SchoolCreate

router = APIRouter(prefix="/schools", tags=["schools"], route_class=WrappedRoute)

@router.post(
    "",
    description="Requires the ADMIN role.",
    response_model=Response[SchoolResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def create_school(
     dto: Annotated[SchoolCreate, Body()], 
     _: Roles(Role.ADMIN),
     service: SchoolService = Depends(get_school_service)):
    return await service.create_school(dto)

@router.get(
    "/{school_id}",
    description="Get a school by ID. Requires the TEACHER role.",
    response_model=Response[SchoolResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_school(
     school_id: Annotated[int, Path(title="The ID of the school")],
     teacher: Roles(Role.TEACHER),
     service: SchoolService = Depends(get_school_service)):
    school = await service.get_school(school_id, teacher.profile_id)
    return Response(
        data=school,
        message=get_response_message()
    )


@router.get(
    "/city/{city_id}",
    description="Get a list of school by city ID. Requires the TEACHER role.",
    response_model=Response[list[SchoolResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def get_list_school(
     city_id: Annotated[int, Path(title="The ID of the city")],
     _ : Roles(Role.TEACHER),
     service: SchoolService = Depends(get_school_service)):
    schools = await service.get_list_school(city_id)
    return Response(
        data=schools,
        message=get_response_message()
    )

