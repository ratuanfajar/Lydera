from fastapi import APIRouter, Depends, status

from app.core.response import Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_curriculum_service
from app.domains.contents.schemas import FaseResponse
from app.domains.contents.services.curriculum_service import CurriculumService
from app.utils.role import Role

router_fases = APIRouter(prefix="/fases", tags=["fases"], route_class=WrappedRoute)


@router_fases.get(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[list[FaseResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_fase(
    _: Roles(Role.TEACHER),
    service: CurriculumService = Depends(get_curriculum_service),
):
    fases = await service.get_all_fases()
    return Response(
        message=get_response_message(),
        data=fases,
    )
