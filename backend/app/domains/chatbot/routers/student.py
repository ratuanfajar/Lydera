from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path as FastAPIPath, Query, status

from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.chatbot.depedencies import get_chatbot_service
from app.domains.chatbot.schemas import (
    ChatAnswerResponse,
    ChatAskRequest,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)
from app.domains.chatbot.schemas.chat import ChatSessionQuery, ChatSessionResponseWithMessage
from app.domains.chatbot.services import ChatbotService
from app.utils.role import Role

router_chatbot_student = APIRouter(
    prefix="/chatbot",
    tags=["chatbot"],
    route_class=WrappedRoute,
)


@router_chatbot_student.post(
    "/sessions",
    description=(
        "Requires the STUDENT role. Mulai sesi tanya-jawab baru, di-scope ke satu "
        "classroom -- retrieval otomatis lintas semua chapter published di classroom "
        "itu, tidak perlu pilih chapter_id manual."
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
    return Response(
        message=get_response_message(),
        data={"id": session.id, "classroom_id": session.classroom_id},
    )


@router_chatbot_student.post(
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
            "suggested_questions": result.get("suggested_questions"),
            "scope_klass": result["scope"]["klass"],
        },
    )


@router_chatbot_student.get(
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
        data=sessions,
    )


@router_chatbot_student.get(
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
