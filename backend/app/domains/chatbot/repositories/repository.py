from typing import Sequence

from sqlalchemy import delete, exists, select

from app.core.db import AsyncSession
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models import Block, Chapter, Module, ModuleStatus
from app.domains.chatbot.models import BlockEmbedding, ChapterKb, ChatMessage, ChatSession
from app.domains.users.models.student import student_classrooms


class ChatbotRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Content lookup (dipakai reindex) ---

    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]:
        stmt = select(Block).where(Block.chapter_id == chapter_id).order_by(Block.reading_order)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_chapter_ids_for_classroom(self, classroom_id: int) -> Sequence[int]:
        """Semua chapter di module yang published dalam satu classroom -- dipakai reindex massal
        (`POST /chatbot/classrooms/{id}/reindex`), supaya guru tidak perlu reindex satu-satu."""
        stmt = (
            select(Chapter.id)
            .join(Module, Module.id == Chapter.module_id)
            .where(Module.classroom_id == classroom_id, Module.status == ModuleStatus.PUBLISH)
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def verify_classroom_teacher(self, classroom_id: int, teacher_id: int) -> bool:
        stmt = select(
            exists().where(Classroom.id == classroom_id, Classroom.teacher_id == teacher_id)
        )
        return bool(await self.db.scalar(stmt))

    async def validate_student_classroom_access(self, classroom_id: int, student_id: int) -> bool:
        stmt = select(
            exists()
            .where(student_classrooms.c.classroom_id == classroom_id)
            .where(student_classrooms.c.student_id == student_id)
        )
        return bool(await self.db.scalar(stmt))

    # --- Knowledge base (embeddings) ---

    async def get_chapter_kb(self, chapter_id: int) -> ChapterKb | None:
        return await self.db.get(ChapterKb, chapter_id)

    async def bump_chapter_kb_version(self, chapter_id: int) -> ChapterKb:
        kb = await self.get_chapter_kb(chapter_id)
        if kb is None:
            kb = ChapterKb(chapter_id=chapter_id, kb_version=1)
            self.db.add(kb)
        else:
            kb.kb_version += 1
        await self.db.flush()
        return kb

    async def replace_block_embeddings(self, chapter_id: int, kb_version: int, chunks: list[dict]) -> None:
        """Ganti seluruh chunk embedding satu bab dengan versi baru (reindex penuh, bukan
        incremental -- volume per bab kecil, jadi tidak perlu diff)."""
        await self.db.execute(delete(BlockEmbedding).where(BlockEmbedding.chapter_id == chapter_id))
        for chunk in chunks:
            self.db.add(
                BlockEmbedding(
                    chapter_id=chapter_id,
                    block_ids=chunk["block_ids"],
                    heading=chunk["heading"],
                    chunk_text=chunk["text"],
                    embedding=chunk["embedding"],
                    kb_version=kb_version,
                )
            )
        await self.db.flush()

    # --- Chat session/message ---

    async def create_session(self, student_id: int, classroom_id: int) -> ChatSession:
        session = ChatSession(student_id=student_id, classroom_id=classroom_id)
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(self, session_id: int, student_id: int) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.student_id == student_id)
        result = await self.db.scalars(stmt)
        return result.first()

    async def get_recent_messages(self, session_id: int, limit: int) -> Sequence[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        result = await self.db.scalars(stmt)
        return list(reversed(result.all()))

    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        tool_calls: list | None = None,
        citations: list | None = None,
        scope_klass: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            citations=citations,
            scope_klass=scope_klass,
        )
        self.db.add(message)
        await self.db.flush()
        return message
