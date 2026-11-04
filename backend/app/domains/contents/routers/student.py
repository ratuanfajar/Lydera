from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, Query

from app.core.response import Response
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import (
    get_chapter_service,
    get_module_service,
    get_note_service,
)
from app.domains.contents.schemas.chapters.student_chapter_detail_response import (
    StudentChapterDetailResponse,
)
from app.domains.contents.schemas.module.student_module_detail_request import (
    StudentModuleDetailRequest,
)
from app.domains.contents.schemas.module.student_module_request import StudentModuleRequest
from app.domains.contents.schemas.module.student_module_response import (
    StudentModuleResponse,
    StudentModuleWithoutChaptersResponse,
)
from app.domains.contents.schemas.record_note.record_note_create import RecordNoteCreate
from app.domains.contents.schemas.record_note.record_note_request import RecordNoteRequest
from app.domains.contents.schemas.record_note.record_note_response import RecordNoteResponse
from app.domains.contents.services.chapter_service import ChapterService
from app.domains.contents.services.module_service import ModuleService
from app.domains.contents.services.note_service import RecordNoteService
from app.utils.role import Role

router_student_contents = APIRouter(
    prefix="/students",
    tags=["students"],
    route_class=WrappedRoute,
)


@router_student_contents.get(
    "/modules",
    response_model=Response[list[StudentModuleWithoutChaptersResponse]],
    description="Requires the STUDENT role.",
)
async def get_all_modules_student(
    query: Annotated[StudentModuleRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: ModuleService = Depends(get_module_service),
):
    result = await service.get_student_modules(
        query,
        student_id=student.profile_id,
    )
    return Response(
        message="Berhasil mendapatkan data tasks",
        data=result,
    )


@router_student_contents.get(
    "/modules/{module_id}",
    response_model=Response[StudentModuleResponse],
    description="Requires the STUDENT role.",
)
async def get_detail_module_student(
    module_id: Annotated[int, FastAPIPath()],
    query: Annotated[StudentModuleDetailRequest, Depends()],
    student: Roles(Role.STUDENT),
    service: ModuleService = Depends(get_module_service),
):
    result = await service.get_student_module(
        query,
        student_id=student.profile_id,
        module_id=module_id,
    )
    return Response(
        message="Berhasil mendapatkan data module",
        data=result,
    )


@router_student_contents.post(
    "/chapters/{chapter_id}/start",
    response_model=Response[StudentChapterDetailResponse],
    description="Requires the STUDENT role.",
)
async def get_detail_chapter_student(
    chapter_id: Annotated[int, FastAPIPath()],
    student: Roles(Role.STUDENT),
    service: ChapterService = Depends(get_chapter_service),
):
    result = await service.start_chapter(
        student_id=student.profile_id,
        chapter_id=chapter_id,
    )
    return Response(
        message="Berhasil mendapatkan data detail chapter",
        data=result,
    )


@router_student_contents.post(
    "/chapters/{chapter_id}/mark-complete",
    response_model=Response[bool],
    description="Requires the STUDENT role.",
)
async def mark_chapter(
    chapter_id: Annotated[int, FastAPIPath()],
    student: Roles(Role.STUDENT),
    service: ChapterService = Depends(get_chapter_service),
):
    result = await service.mark_chapter_as_completed(
        student_id=student.profile_id,
        chapter_id=chapter_id,
    )
    return Response(
        message="Selamat telah menyelesaikan chapter",
        data=result,
    )


@router_student_contents.get(
    "/record-note",
    response_model=Response[Optional[RecordNoteResponse]],
    description="Requires the STUDENT role.",
)
async def get_record_note_chapter(
    query: Annotated[RecordNoteRequest, Query()],
    student: Roles(Role.STUDENT),
    service: RecordNoteService = Depends(get_note_service),
):
    result = await service.get_record_note(
        student_id=student.profile_id,
        chapter_id=query.chapter_id,
    )
    return Response(
        message="Berhasil mendapatkan data catatan",
        data=result,
    )


@router_student_contents.post(
    "/record-note",
    response_model=Response[RecordNoteResponse],
    description="Requires the STUDENT role.",
)
async def save_note(
    student: Roles(Role.STUDENT),
    body: Annotated[RecordNoteCreate, Body()],
    service: RecordNoteService = Depends(get_note_service),
):
    result = await service.save_record_note(
        student_id=student.profile_id,
        dto=body,
    )
    return Response(
        message="Berhasil menyimpan catatan",
        data=result,
    )
