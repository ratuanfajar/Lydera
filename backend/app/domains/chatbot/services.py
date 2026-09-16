from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.core.db import AsyncSession
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.redis import get_redis_client
from app.domains.chatbot.models import ChatSession
from app.domains.chatbot.repositories.repository import ChatbotRepository
from app.domains.chatbot.sync_search import make_search_module_executor
from app.utils import paths
from app.domains.chatbot.schemas.chat import ChatSessionResponseWithMessage

paths.setup()
from chatbot import agent as chatbot_agent  # noqa: E402  (ai-services/chatbot/agent.py)
from chatbot import chunk as chatbot_chunk  # noqa: E402  (ai-services/chatbot/chunk.py)
from chatbot import llm_ext  # noqa: E402  (ai-services/chatbot/llm_ext.py)
from annotation import config as ai_config  # noqa: E402


def _history_key(session_id: int) -> str:
    return f"chatbot:history:{session_id}"


class ChatbotService:
    def __init__(self, repo: ChatbotRepository, db: AsyncSession):
        self.repo = repo
        self.db = db

    # --- Reindex (dipanggil guru setelah publish bab) ---

    async def reindex_chapter(self, chapter_id: int) -> dict:
        blocks = await self.repo.get_blocks_for_chapter(chapter_id)
        if not blocks:
            raise BadRequestException("Bab ini belum punya block untuk diindeks (atau bab tidak ditemukan)")

        blocks_as_rows = [
            {"id": b.id, "block_type": b.block_type, "readable_text": b.readable_text, "reading_order": b.reading_order}
            for b in blocks
        ]
        chunks = await asyncio.to_thread(chatbot_chunk.build_chunks, chapter_id, blocks_as_rows)
        if not chunks:
            raise BadRequestException("Tidak ada chunk yang bisa dibentuk dari bab ini")

        embeddings = await asyncio.to_thread(llm_ext.embed_texts, [c.text for c in chunks])

        kb = await self.repo.bump_chapter_kb_version(chapter_id)
        await self.repo.replace_block_embeddings(
            chapter_id,
            kb.kb_version,
            [
                {"block_ids": c.block_ids, "heading": c.heading, "text": c.text, "embedding": emb}
                for c, emb in zip(chunks, embeddings)
            ],
        )
        await self.db.commit()
        return {"chapter_id": chapter_id, "kb_version": kb.kb_version, "chunks_indexed": len(chunks)}

    async def verify_classroom_teacher(self, classroom_id: int, teacher_id: int) -> bool:
        return await self.repo.verify_classroom_teacher(classroom_id, teacher_id)

    # --- Sesi ---

    async def start_session(self, student_id: int, classroom_id: int) -> ChatSession:
        has_access = await self.repo.validate_student_classroom_access(classroom_id, student_id)
        if not has_access:
            raise ForbiddenException("Anda tidak memiliki akses ke kelas ini.")
        session = await self.repo.create_session(student_id, classroom_id)
        await self.db.commit()
        return session

    async def list_session(self, student_id:int, classroom_id:int) -> list[ChatSessionResponseWithMessage]:
        result = await self.repo.get_list_sessions(student_id, classroom_id)
        return result
    # --- Tanya jawab ---

    async def ask(self, session_id: int, student_id: int, question: str) -> dict:
        session = await self.repo.get_session(session_id, student_id)
        if session is None:
            raise NotFoundException("Sesi chat tidak ditemukan")

        history = await self._get_history(session_id)
        search_module_executor = make_search_module_executor(session.classroom_id, ai_config.TOP_K_CHUNKS)

        result = await asyncio.to_thread(chatbot_agent.run, question, history, search_module_executor)

        await self.repo.add_message(session_id, "user", question)
        await self.repo.add_message(
            session_id,
            "assistant",
            result["message"],
            tool_calls=result.get("tool_calls"),
            citations=result.get("sources"),
            scope_klass=result["scope"]["klass"],
        )
        await self.db.commit()
        await self._push_history(session_id, question, result["message"])

        return result

    async def get_history(self, session_id: int, student_id: int) -> list:
        session = await self.repo.get_session(session_id, student_id)
        if session is None:
            raise NotFoundException("Sesi chat tidak ditemukan")
        return await self.repo.get_recent_messages(session_id, settings.CHAT_HISTORY_TURNS * 2)

    # --- Conversation state (Redis hot cache, fallback ke Postgres kalau kosong) ---

    async def _get_history(self, session_id: int) -> list[dict]:
        redis_client = get_redis_client()
        cached = await redis_client.lrange(_history_key(session_id), 0, -1)
        if cached:
            return [json.loads(item) for item in cached]

        messages = await self.repo.get_recent_messages(session_id, settings.CHAT_HISTORY_TURNS * 2)
        return [{"role": m.role, "content": m.content} for m in messages]

    async def _push_history(self, session_id: int, question: str, answer: str) -> None:
        redis_client = get_redis_client()
        key = _history_key(session_id)
        await redis_client.rpush(
            key,
            json.dumps({"role": "user", "content": question}),
            json.dumps({"role": "assistant", "content": answer}),
        )
        await redis_client.ltrim(key, -(settings.CHAT_HISTORY_TURNS * 2), -1)
        await redis_client.expire(key, settings.CHAT_HISTORY_TTL_SECONDS)
