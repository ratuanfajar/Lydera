from fastapi import APIRouter, Depends

from app.core.response import Response
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_block_service
from app.domains.contents.schemas import RegenerateRequest, RegenerateResponse
from app.domains.contents.schemas.blocks.regenerate_response import RegenerateDetailResponse
from app.domains.contents.services.block_service import BlockService
from app.domains.jobs.depedencies import get_job_service
from app.domains.jobs.services import JobService
from app.utils.role import Role

router_blocks = APIRouter(prefix="/blocks", tags=["blocks"], route_class=WrappedRoute)


@router_blocks.post("/bulk-regenerate/text", response_model=Response[RegenerateResponse])
async def bulk_regenerate_text(
    payload: RegenerateRequest,
    teacher: Roles(Role.TEACHER),
    service: BlockService = Depends(get_block_service),
):
    result = await service.regenerate_text_blocks(payload, teacher.profile_id)
    return Response(message="Text blocks updated successfully", data=result)


@router_blocks.post(
    "/bulk-regenerate/special",
    response_model=Response[list[RegenerateDetailResponse]],
)
async def bulk_regenerate_special(
    payload: RegenerateRequest,
    teacher: Roles(Role.TEACHER),
    service: BlockService = Depends(get_block_service),
    job_service: JobService = Depends(get_job_service),
):
    result = await service.regenerate_special_blocks(
        payload,
        teacher.profile_id,
        job_service,
    )
    return Response(message="Special blocks regenerated via AI", data=result)
