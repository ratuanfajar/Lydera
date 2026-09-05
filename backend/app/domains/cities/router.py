from fastapi import APIRouter, Depends, status, Body
from core.route import WrappedRoute
from typing import Annotated
from domains.cities.depedencies import get_city_service
from domains.cities.services import CityService
from core.response import Response
from domains.cities.schemas import CityResponse, CityCreate

router = APIRouter(prefix="/cities", tags=["cities"], route_class=WrappedRoute)


@router.get(
    "",
    response_model=Response[list[CityResponse]])
async def get_cities(service: CityService = Depends(get_city_service)):
    return await service.get_list_city()


@router.post(
    "",
    response_model=Response[str],
    status_code=status.HTTP_201_CREATED,
)
async def create_city(
     city: Annotated[CityCreate, Body()], 
     service: CityService = Depends(get_city_service)):
    return await service.create_city(city)
