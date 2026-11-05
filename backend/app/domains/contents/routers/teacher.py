from typing import Annotated

from fastapi import APIRouter, Depends, Path as FastAPIPath

from app.core.response import COMMON_VALIDATION_RESPONSES, Response
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_chapter_service, get_module_service
from app.domains.contents.schemas.chapters.chapter_detail_response import ChapterDetailResponse
from app.domains.contents.schemas.module.teacher_module_detail_request import (
    TeacherModuleDetailRequest,
)
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleRequest
from app.domains.contents.schemas.module.teacher_module_response import (
    TeacherModuleResponse,
    TeacherModuleWithoutChapterResponse,
)
from app.domains.contents.services.chapter_service import ChapterService
from app.domains.contents.services.module_service import ModuleService
from app.utils.role import Role

router_teacher_contents = APIRouter(
    prefix="/teachers",
    tags=["teachers"],
    route_class=WrappedRoute,
)


@router_teacher_contents.get(
    "/modules",
    response_model=Response[list[TeacherModuleWithoutChapterResponse]],
    description="Requires the Teacher role.",
)
async def get_all_modules_teacher(
    query: Annotated[TeacherModuleRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    service: ModuleService = Depends(get_module_service),
):
    result = await service.get_teacher_modules(
        query,
        teacher_id=teacher.profile_id,
    )
    return Response(
        message="Berhasil mendapatkan data modules",
        data=result,
    )


@router_teacher_contents.get(
    "/modules/{module_id}",
    response_model=Response[TeacherModuleResponse],
    description="Requires the Teacher role.",
)
async def get_module_teacher(
    query: Annotated[TeacherModuleDetailRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    module_id: int,
    service: ModuleService = Depends(get_module_service),
):
    result = await service.get_teacher_module(
        query,
        module_id,
        teacher_id=teacher.profile_id,
    )
    return Response(
        message="Berhasil mendapatkan data modules",
        data=result,
    )


@router_teacher_contents.delete(
    "/modules/{module_id}",
    response_model=Response[bool],
    description="Requires the Teacher role.",
)
async def delete_module_teacher(
    query: Annotated[TeacherModuleDetailRequest, Depends()],
    teacher: Roles(Role.TEACHER),
    module_id: int,
    service: ModuleService = Depends(get_module_service),
):
    result = await service.delete_module(
        teacher.profile_id,
        query.classroom_id,
        module_id,
    )
    return Response(
        message="Berhasil menghapus data module",
        data=result,
    )


@router_teacher_contents.get(
    "/chapters/{chapter_id}",
    description="Requires the TEACHER role.",
    response_model=Response[ChapterDetailResponse],
    responses=COMMON_VALIDATION_RESPONSES,
)
async def get_chapter_by_id(
    chapter_id: Annotated[int, FastAPIPath()],
    teacher: Roles(Role.TEACHER),
    service: ChapterService = Depends(get_chapter_service),
):
    result = await service.get_chapter_by_id(chapter_id, teacher.profile_id)
    return Response(
        message="Chapter berhasil didapat",
        data=result,
    )
