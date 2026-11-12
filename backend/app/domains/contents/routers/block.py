
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status, Path as FastAPIPath

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_block_service
from app.domains.contents.schemas import RegenerateRequest, RegenerateResponse
from app.domains.contents.schemas.blocks.regenerate_response import RegenerateDetailResponse
from app.domains.contents.services.block_service import BlockService
from app.domains.jobs.depedencies import get_job_service
from app.domains.jobs.services import JobService
from app.utils.role import Role
from app.domains.contents.schemas.blocks.block_edit import BlockEditRequest, BlockEditResponse

router_blocks = APIRouter(prefix="/blocks", tags=["blocks"], route_class=WrappedRoute)

@router_blocks.delete(
    "/{block_id}",
    response_model=Response[None],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def delete_block_by_id(
    block_id: Annotated[int, FastAPIPath()],
    teacher: Roles(Role.TEACHER),
    service: BlockService = Depends(get_block_service),
):
    result = await service.delete_block_by_id(block_id)
    return Response(message="Delete block successfully", data=None)

@router_blocks.patch(
    "/{block_id}",
    description=(
        "Requires the TEACHER role. Edit langsung satu blok. Rumus: source_markup (LaTeX) atau readable_text. "
        "Tabel: tabel terstruktur atau readable_text. Gambar, teks, heading: readable_text. readable_text yang dikirim dipakai apa adanya."
    ),
    response_model=Response[BlockEditResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def edit_block(
    block_id: Annotated[int, FastAPIPath()],
    payload: Annotated[BlockEditRequest, Body()],
    teacher: Roles(Role.TEACHER),
    service: BlockService = Depends(get_block_service),
):
    result = await service.edit_block(block_id, teacher.profile_id, payload)
    return Response(message=get_response_message(), data=result)

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
    try:
        result = await service.regenerate_special_blocks(payload, teacher.profile_id, job_service)
        return Response(message="Special blocks regenerated via AI", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
