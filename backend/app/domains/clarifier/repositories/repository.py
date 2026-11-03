from typing import Sequence

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSession
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models import Block, Chapter, Module, ModuleStatus
from app.domains.clarifier.models import BlockEmbedding, ChapterKb, ChatMessage, ChatSession
from app.domains.quizzer.models import QuizProgress, QuizRequest
from app.domains.users.models.student import student_classrooms
from app.domains.clarifier.schemas.chat import ChatSessionResponseWithMessage


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
        (`POST /clarifier/classrooms/{id}/reindex`), supaya guru tidak perlu reindex satu-satu."""
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

    async def verify_chapter_teacher(self, chapter_id: int, teacher_id: int) -> bool:
        stmt = (
            select(Chapter.id)
            .join(Module, Chapter.module_id == Module.id)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(Chapter.id == chapter_id, Classroom.teacher_id == teacher_id)
        )
        return (await self.db.execute(stmt)).first() is not None

    async def validate_student_classroom_access(self, classroom_id: int, student_id: int) -> bool:
        stmt = select(
            exists()
            .where(student_classrooms.c.classroom_id == classroom_id)
            .where(student_classrooms.c.student_id == student_id)
        )
        return bool(await self.db.scalar(stmt))

    async def get_started_unfinished_quizzes(self, classroom_id: int, student_id: int) -> Sequence[tuple[QuizProgress, QuizRequest]]:
        stmt = (
            select(QuizProgress, QuizRequest)
            .join(QuizRequest, QuizRequest.id == QuizProgress.quiz_request_id)
            .where(
                QuizRequest.classroom_id == classroom_id,
                QuizProgress.student_id == student_id,
                QuizProgress.started_at.is_not(None),
                QuizProgress.is_done.is_(False),
            )
        )
        return (await self.db.execute(stmt)).all()

    async def get_visual_blocks_for_references(self, classroom_id: int, references: list[int]) -> dict[int, list[Block]]:
        """Blok tabel dan gambar (bukan dekoratif) pada chunk yang dirujuk tiap `reference` (id blok pertama chunk), hanya dari modul publish di kelas."""
        if not references:
            return {}
        chunk_stmt = (
            select(BlockEmbedding.block_ids)
            .join(Chapter, Chapter.id == BlockEmbedding.chapter_id)
            .join(Module, Module.id == Chapter.module_id)
            .where(Module.classroom_id == classroom_id, Module.status == ModuleStatus.PUBLISH, BlockEmbedding.block_ids[1].in_(references))
        )
        chunks = {ids[0]: list(ids) for ids in (await self.db.scalars(chunk_stmt)).all() if ids}
        wanted = {block_id for ids in chunks.values() for block_id in ids}
        if not wanted:
            return {}
        block_stmt = select(Block).where(
            Block.id.in_(wanted), Block.block_type.in_(("table", "image")), Block.image_kind.is_distinct_from("dekoratif"),
        ).order_by(Block.reading_order)
        by_id = {block.id: block for block in (await self.db.scalars(block_stmt)).all()}
        return {reference: [by_id[i] for i in ids if i in by_id] for reference, ids in chunks.items()}

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
                    formula_norm=chunk["formula_norm"],
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

    async def get_list_sessions(self, student_id:int, classroom_id:int) -> list[ChatSessionResponseWithMessage]:
        latest_message_subquery = (
            select(ChatMessage.content)
            .where(ChatMessage.session_id == ChatSession.id)
            .order_by(ChatMessage.id.asc())
            .limit(1)
            .scalar_subquery()
        )

        stmt = (
            select(
                ChatSession.id,
                ChatSession.classroom_id,
                latest_message_subquery.label("first_message"),
            )
            .where(
                ChatSession.student_id == student_id,
                ChatSession.classroom_id == classroom_id,
            )
        )

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [ChatSessionResponseWithMessage.model_validate(row) for row in rows]

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
        content_markup: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            content_markup=content_markup,
            tool_calls=tool_calls,
            citations=citations,
            scope_klass=scope_klass,
        )
        self.db.add(message)
        await self.db.flush()
        return message
