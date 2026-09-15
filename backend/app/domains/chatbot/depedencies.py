from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.domains.chatbot.repositories.repository import ChatbotRepository
from app.domains.chatbot.services import ChatbotService


def get_chatbot_repository(db: AsyncSession = Depends(get_db)) -> ChatbotRepository:
    return ChatbotRepository(db)


def get_chatbot_service(
    repo: ChatbotRepository = Depends(get_chatbot_repository), db: AsyncSession = Depends(get_db)
) -> ChatbotService:
    return ChatbotService(repo, db)
