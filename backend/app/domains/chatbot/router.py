from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, Query, status

from app.core.response import Response, get_response_message, COMMON_VALIDATION_RESPONSES
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.utils.role import Role
from app.domains.chatbot.depedencies import get_chatbot_service
from app.core.exceptions import ForbiddenException
from app.domains.chatbot.schemas import (
    ChatAnswerResponse,
    ChatAskRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ReindexClassroomQueuedResponse,
    ReindexQueuedResponse,
)
from app.domains.chatbot.services import ChatbotService
from app.tasks.chatbot_tasks import reindex_chapter_task, reindex_classroom_task
from app.domains.chatbot.schemas.chat import ChatSessionQuery, ChatSessionResponseWithMessage

router_chatbot = APIRouter(prefix="/chatbot", tags=["chatbot"], route_class=WrappedRoute)


@router_chatbot.post(
    "/chapters/{chapter_id}/reindex",
    description=(
        "Requires the TEACHER role. Bangun ulang knowledge base (embedding) chatbot untuk bab ini -- "
        "panggil setelah publish/edit modul supaya jawaban chatbot ikut sumber terbaru. Diproses "
        "async lewat taskiq (mirip quiz generator), supaya request ini tidak menunggu batch call "
        "embedding API selesai."
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
    return Response(message=get_response_message(), data={"chapter_id": chapter_id, "status": "queued"})


@router_chatbot.post(
    "/classrooms/{classroom_id}/reindex",
    description=(
        "Requires the TEACHER role. Reindex SEMUA chapter published di satu classroom sekaligus -- "
        "supaya tidak perlu panggil reindex per-chapter manual satu-satu. Tiap chapter tetap "
        "diproses sebagai task terpisah (lihat app/tasks/chatbot_tasks.py)."
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
    is_owner = await service.verify_classroom_teacher(classroom_id, teacher.profile_id)
    if not is_owner:
        raise ForbiddenException("Anda bukan pengajar classroom ini.")
    await reindex_classroom_task.kiq(classroom_id=classroom_id)
    return Response(message=get_response_message(), data={"classroom_id": classroom_id, "status": "queued"})


@router_chatbot.post(
    "/sessions",
    description=(
        "Requires the STUDENT role. Mulai sesi tanya-jawab baru, di-scope ke satu classroom -- "
        "retrieval otomatis lintas semua chapter published di classroom itu, tidak perlu pilih "
        "chapter_id manual."
    ),
    response_model=Response[ChatSessionResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def create_session(
    student: Roles(Role.STUDENT),
    payload: Annotated[ChatSessionCreate, Body()],
    service: ChatbotService = Depends(get_chatbot_service),
):
    session = await service.start_session(student.profile_id, payload.classroom_id)
    return Response(message=get_response_message(), data={"id": session.id, "classroom_id": session.classroom_id})


@router_chatbot.post(
    "/sessions/{session_id}/messages",
    description="Requires the STUDENT role. Ajukan pertanyaan ke chatbot dalam sesi ini.",
    response_model=Response[ChatAnswerResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def ask_question(
    student: Roles(Role.STUDENT),
    session_id: Annotated[int, FastAPIPath()],
    payload: Annotated[ChatAskRequest, Body()],
    service: ChatbotService = Depends(get_chatbot_service),
):
    result = await service.ask(session_id, student.profile_id, payload.question)
    return Response(
        message=get_response_message(),
        data={
            "status": result["status"],
            "message": result["message"],
            "sources": result.get("sources"),
            "scope_klass": result["scope"]["klass"],
        },
    )

@router_chatbot.get(
    "/sessions",
    description="Requires the STUDENT role. Riwayat sesi.",
    response_model=Response[list[ChatSessionResponseWithMessage]],
    status_code=status.HTTP_200_OK,
)
async def list_sessions(
    student: Roles(Role.STUDENT),
    query: Annotated[ChatSessionQuery, Query()],
    service: ChatbotService = Depends(get_chatbot_service),
):
    sessions = await service.list_session(query.classroom_id, student.profile_id)
    return Response(
        message=get_response_message(),
        data=sessions
    )


@router_chatbot.get(
    "/sessions/{session_id}/messages",
    description="Requires the STUDENT role. Riwayat pesan dalam sesi ini.",
    response_model=Response[list[ChatMessageResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_messages(
    student: Roles(Role.STUDENT),
    session_id: Annotated[int, FastAPIPath()],
    service: ChatbotService = Depends(get_chatbot_service),
):
    messages = await service.get_history(session_id, student.profile_id)
    return Response(
        message=get_response_message(),
        data=[
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": m.citations,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    )
