from fastapi import APIRouter, Depends, status, Body
from app.utils.role import Role
from app.core.security import Roles
from app.core.route import WrappedRoute
from typing import Annotated
from app.domains.cities.depedencies import get_city_service
from app.domains.cities.services import CityService
from app.core.response import COMMON_VALIDATION_RESPONSES, Response
from app.domains.cities.schemas import CityResponse, CityCreate

router = APIRouter(prefix="/cities", tags=["cities"], route_class=WrappedRoute)


@router.get(
    "",
    description="Requires the ADMIN role.",
    response_model=Response[list[CityResponse]])
async def get_cities(
     current_user: Roles(Role.ADMIN),
     service: CityService = Depends(get_city_service)):
    return await service.get_list_city()


@router.post(
    "",
    description="Requires the ADMIN role.",
    response_model=Response[CityResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def create_city(
     current_user: Roles(Role.ADMIN),
     dto: Annotated[CityCreate, Body()], 
     service: CityService = Depends(get_city_service)):
     return await service.create_city(dto)
