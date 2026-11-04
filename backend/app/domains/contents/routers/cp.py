from typing import Annotated

from fastapi import APIRouter, Depends, Path as FastAPIPath, status

from app.core.response import COMMON_VALIDATION_RESPONSES, Response
from app.core.route import WrappedRoute
from app.domains.contents.depedencies import get_curriculum_service
from app.domains.contents.schemas import CpResponse
from app.domains.contents.services.curriculum_service import CurriculumService

router_cps = APIRouter(prefix="/cp", tags=["cp"], route_class=WrappedRoute)


@router_cps.get(
    "/{fase_id}",
    description="List of cp",
    response_model=Response[list[CpResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_cps_by_fase_id(
    fase_id: Annotated[
        int,
        FastAPIPath(description="Fase id"),
    ],
    service: CurriculumService = Depends(get_curriculum_service),
):
    result = await service.get_cps_by_fase_id(fase_id)
    return Response(
        message="Cp loaded successfully",
        data=result,
    )
