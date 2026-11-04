from typing import Annotated

from fastapi import APIRouter, Depends, Path as FastAPIPath, status

from app.core.exceptions import ForbiddenException
from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.chatbot.depedencies import get_chatbot_service
from app.domains.chatbot.schemas import ReindexClassroomQueuedResponse, ReindexQueuedResponse
from app.domains.chatbot.services import ChatbotService
from app.tasks.chatbot_tasks import reindex_chapter_task, reindex_classroom_task
from app.utils.role import Role

router_chatbot_teacher = APIRouter(
    prefix="/chatbot",
    tags=["chatbot"],
    route_class=WrappedRoute,
)


@router_chatbot_teacher.post(
    "/chapters/{chapter_id}/reindex",
    description=(
        "Requires the TEACHER role. Bangun ulang knowledge base (embedding) chatbot "
        "untuk bab ini -- panggil setelah publish/edit modul supaya jawaban chatbot "
        "ikut sumber terbaru. Diproses async lewat taskiq (mirip quiz generator), "
        "supaya request ini tidak menunggu batch call embedding API selesai."
    ),
    response_model=Response[ReindexQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def reindex_chapter(
    _: Roles(Role.TEACHER),
    chapter_id: Annotated[int, FastAPIPath()],
):
    await reindex_chapter_task.kiq(chapter_id=chapter_id)
    return Response(
        message=get_response_message(),
        data={"chapter_id": chapter_id, "status": "queued"},
    )


@router_chatbot_teacher.post(
    "/classrooms/{classroom_id}/reindex",
    description=(
        "Requires the TEACHER role. Reindex SEMUA chapter published di satu classroom "
        "sekaligus -- supaya tidak perlu panggil reindex per-chapter manual satu-satu. "
        "Tiap chapter tetap diproses sebagai task terpisah "
        "(lihat app/tasks/chatbot_tasks.py)."
    ),
    response_model=Response[ReindexClassroomQueuedResponse],
    status_code=status.HTTP_202_ACCEPTED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def reindex_classroom(
    teacher: Roles(Role.TEACHER),
    classroom_id: Annotated[int, FastAPIPath()],
    service: ChatbotService = Depends(get_chatbot_service),
):
    is_owner = await service.verify_classroom_teacher(
        classroom_id,
        teacher.profile_id,
    )
    if not is_owner:
        raise ForbiddenException("Anda bukan pengajar classroom ini.")
    await reindex_classroom_task.kiq(classroom_id=classroom_id)
    return Response(
        message=get_response_message(),
        data={"classroom_id": classroom_id, "status": "queued"},
    )
