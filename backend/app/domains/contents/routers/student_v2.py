from typing import Annotated

from fastapi import APIRouter, Depends, Path as FastAPIPath, Query

from app.core.response import Response
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_chapter_service
from app.domains.contents.schemas.chapters.student_chapter_detail_response import (
    StudentChapterDetailV2Response,
)
from app.domains.contents.services.chapter_service import ChapterService
from app.utils.role import Role

router_student_contents_v2 = APIRouter(
    prefix="/v2/students",
    tags=["students-v2"],
    route_class=WrappedRoute,
)


@router_student_contents_v2.post(
    "/chapters/{chapter_id}/start",
    response_model=Response[StudentChapterDetailV2Response],
    description="Requires the STUDENT role. Paginated blocks (10 per page default).",
)
async def get_detail_chapter_student_v2(
    chapter_id: Annotated[int, FastAPIPath()],
    student: Roles(Role.STUDENT),
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=50)] = 10,
    service: ChapterService = Depends(get_chapter_service),
):
    result = await service.start_chapter_v2(
        student_id=student.profile_id,
        chapter_id=chapter_id,
        page=page,
        per_page=per_page,
    )
    return Response(
        message="Berhasil mendapatkan data detail chapter",
        data=result,
    )
