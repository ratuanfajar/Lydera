from fastapi import APIRouter, Depends, status, Body
from core.route import WrappedRoute
from typing import Annotated
from domains.schools.depedencies import get_school_service
from domains.schools.services import SchoolService
from core.response import Response
from domains.schools.schemas import SchoolResponse, SchoolCreate

router = APIRouter(prefix="/schools", tags=["schools"], route_class=WrappedRoute)

@router.post(
    "",
    response_model=Response[SchoolResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_school(
     dto: Annotated[SchoolCreate, Body()], 
     service: SchoolService = Depends(get_school_service)):
    return await service.create_school(dto)
