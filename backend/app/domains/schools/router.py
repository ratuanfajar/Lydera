from fastapi import APIRouter, Depends, status, Body
from utils.role import Role
from app.core.route import WrappedRoute
from typing import Annotated
from app.core.security import Roles
from domains.schools.depedencies import get_school_service
from domains.schools.services import SchoolService
from app.core.response import Response, COMMON_VALIDATION_RESPONSES
from domains.schools.schemas import SchoolResponse, SchoolCreate

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
