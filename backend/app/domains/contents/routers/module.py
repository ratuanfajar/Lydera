from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_module_service
from app.domains.contents.schemas import ModuleCreate, ModuleResponse
from app.domains.contents.services.module_service import ModuleService
from app.utils.role import Role

router_modules = APIRouter(prefix="/modules", tags=["modules"], route_class=WrappedRoute)


@router_modules.post(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[ModuleResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def create_module(
    teacher: Roles(Role.TEACHER),
    payload: Annotated[ModuleCreate, Body()],
    service: ModuleService = Depends(get_module_service),
):
    try:
        module = await service.create_module(
            payload.title,
            payload.description,
            payload.status,
            payload.classroom_id,
            teacher.profile_id,
            payload.fase_id,
        )
        return Response(
            message=get_response_message(),
            data=module,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router_modules.post(
    "/publish/{module_id}",
    description="Requires the TEACHER role",
    response_model=Response[bool],
    status_code=status.HTTP_200_OK,
)
async def publish_module(
    module_id: int,
    teacher: Roles(Role.TEACHER),
    service: ModuleService = Depends(get_module_service),
):
    result = await service.publish_module(module_id, teacher.profile_id)
    return Response(
        message="Berhasil publish",
        data=result,
    )

@router_modules.post(
    "/draft/{module_id}",
    description="Requires the TEACHER role",
    response_model=Response[bool],
    status_code=status.HTTP_200_OK,
)
async def draft_module(
    module_id: int,
    teacher: Roles(Role.TEACHER),
    service: ModuleService = Depends(get_module_service),
):
    result = await service.draft_module(module_id, teacher.profile_id)
    return Response(
        message="Berhasil membuat draft",
        data=result,
    )
