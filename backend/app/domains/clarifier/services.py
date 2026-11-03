from __future__ import annotations

import asyncio
import copy
import json
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.db import AsyncSession
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException, TooManyRequestException
from app.core.redis import get_redis_client
from app.domains.clarifier.models import ChatSession
from app.domains.clarifier.repositories.repository import ChatbotRepository
from app.domains.clarifier.sync_search import make_search_module_executor
from app.domains.clarifier.schemas.chat import BlokSumber, ChatSessionResponseWithMessage
from app.utils import paths

paths.setup()
from clarifier import agent as clarifier_agent
from clarifier import chunk as clarifier_chunk
from clarifier import llm_ext
from clarifier import config as ai_config
from clarifier import practice as clarifier_practice
from quizzer import quizzer_pipeline


logger = logging.getLogger(__name__)


def _block_payload(block) -> dict:
    image_url = (
        f"{settings.BASE_URL}/static/annotations/{block.chapter_id}/raw-{block.chapter_id}/auto/images/{block.image_file}"
        if block.image_file else None
    )
    return BlokSumber(
        id=block.id, block_type=block.block_type, readable_text=block.readable_text, caption=block.caption,
        ringkasan=block.ringkasan, tabel=block.tabel, image_url=image_url,
    ).model_dump()


def _history_key(session_id: int) -> str:
    return f"chatbot:history:{session_id}"


def _practice_key(session_id: int) -> str:
    return f"clarifier:practice:{session_id}"


PRACTICE_TTL_SECONDS = 2 * 60 * 60
PRACTICE_RATE_LIMIT = 10
PRACTICE_RATE_WINDOW_SECONDS = 60 * 60
PRACTICE_RATE_MESSAGE = "Kamu sudah banyak meminta latihan. Coba lagi sebentar lagi."
PRACTICE_NO_SOURCE_MESSAGE = "Bagian modul tentang topik yang kamu minta tidak ditemukan di kelasmu. Coba sebut topik dengan kata lain."
PRACTICE_DECLINED_MESSAGE = "Maaf, belum bisa membuat soal latihan yang sesuai dengan modul untuk topik ini. Coba minta lagi atau pilih topik lain."


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
            {
                "id": b.id, "block_type": b.block_type, "readable_text": b.readable_text,
                "reading_order": b.reading_order, "source_markup": b.source_markup,
            }
            for b in blocks
        ]
        chunks = await asyncio.to_thread(clarifier_chunk.build_chunks, chapter_id, blocks_as_rows)
        if not chunks:
            raise BadRequestException("Tidak ada chunk yang bisa dibentuk dari bab ini")

        embeddings = await asyncio.to_thread(llm_ext.embed_texts, [c.text for c in chunks])

        kb = await self.repo.bump_chapter_kb_version(chapter_id)
        await self.repo.replace_block_embeddings(
            chapter_id,
            kb.kb_version,
            [
                {"block_ids": c.block_ids, "heading": c.heading, "text": c.text, "formula_norm": c.formula_norm, "embedding": emb}
                for c, emb in zip(chunks, embeddings)
            ],
        )
        await self.db.commit()
        return {"chapter_id": chapter_id, "kb_version": kb.kb_version, "chunks_indexed": len(chunks)}

    async def verify_classroom_teacher(self, classroom_id: int, teacher_id: int) -> bool:
        return await self.repo.verify_classroom_teacher(classroom_id, teacher_id)

    async def verify_chapter_teacher(self, chapter_id: int, teacher_id: int) -> bool:
        return await self.repo.verify_chapter_teacher(chapter_id, teacher_id)

    # --- Sesi ---

    async def start_session(self, student_id: int, classroom_id: int) -> ChatSession:
        has_access = await self.repo.validate_student_classroom_access(classroom_id, student_id)
        if not has_access:
            raise ForbiddenException("Anda tidak memiliki akses ke kelas ini.")
        session = await self.repo.create_session(student_id, classroom_id)
        await self.db.commit()
        return session

    async def list_session(self, student_id:int, classroom_id:int) -> list[ChatSessionResponseWithMessage]:
        if not await self.repo.validate_student_classroom_access(classroom_id, student_id):
            raise ForbiddenException("Anda tidak memiliki akses ke kelas ini.")
        return await self.repo.get_list_sessions(student_id, classroom_id)
    # --- Tanya jawab ---

    async def _start_practice(self, session_id: int, student_id: int, request: dict, executor) -> dict:
        topic = request["topic"]
        if not topic:
            return clarifier_practice.declined_reply(PRACTICE_NO_SOURCE_MESSAGE)
        await self._ensure_practice_quota(student_id)
        try:
            source = await asyncio.to_thread(clarifier_practice.select_source, topic, executor)
        except Exception:
            logger.exception("pencarian sumber latihan sesi %s gagal", session_id)
            return clarifier_practice.declined_reply(PRACTICE_DECLINED_MESSAGE)
        if source is None:
            return clarifier_practice.declined_reply(PRACTICE_NO_SOURCE_MESSAGE)
        generated = await asyncio.to_thread(quizzer_pipeline.generate_practice, topic, source["text"], request["level"])
        if generated["soal"] is None:
            logger.warning("latihan sesi %s topik %r ditolak: %s", session_id, topic, generated["issues"])
            return clarifier_practice.declined_reply(PRACTICE_DECLINED_MESSAGE)
        stored = clarifier_practice.stored_form(generated["soal"], source["headings"])
        await get_redis_client().set(_practice_key(session_id), json.dumps(stored, ensure_ascii=False), ex=PRACTICE_TTL_SECONDS)
        return clarifier_practice.question_reply(stored)

    async def _ensure_practice_quota(self, student_id: int) -> None:
        redis_client = get_redis_client()
        key = f"clarifier:practice-rate:{student_id}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, PRACTICE_RATE_WINDOW_SECONDS)
        if count > PRACTICE_RATE_LIMIT:
            raise TooManyRequestException(PRACTICE_RATE_MESSAGE)

    async def _answer_practice(self, session_id: int, question: str) -> dict | None:
        choice = clarifier_practice.parse_choice(question)
        if choice is None:
            return None
        raw = await get_redis_client().getdel(_practice_key(session_id))
        return None if raw is None else clarifier_practice.answer_reply(json.loads(raw), choice)

    async def _get_session(self, session_id: int, student_id: int) -> ChatSession:
        session = await self.repo.get_session(session_id, student_id)
        if session is None:
            raise NotFoundException("Sesi chat tidak ditemukan")
        return session

    async def ask(self, session_id: int, student_id: int, question: str) -> dict:
        session = await self._get_session(session_id, student_id)
        await self._ensure_no_active_quiz(session.classroom_id, student_id)

        result, citations = await self._answer_practice(session_id, question), None
        if result is None:
            result, citations = await self._agent_reply(session, session_id, student_id, question)

        await self.repo.add_message(session_id, "user", question)
        await self.repo.add_message(
            session_id,
            "assistant",
            result["message"],
            content_markup=result.get("message_markup"),
            tool_calls=result.get("tool_calls"),
            citations=citations,
            scope_klass=result["scope"]["klass"],
        )
        await self.db.commit()
        if result.get("format_issues"):
            logger.warning("rumus jawaban sesi %s bermasalah: %s", session_id, result["format_issues"])
        try:
            await self._push_history(session_id, question, result.get("message_markup") or result["message"])
        except Exception:
            logger.warning("riwayat Redis sesi %s tidak tersimpan", session_id, exc_info=True)

        return result

    async def _agent_reply(self, session: ChatSession, session_id: int, student_id: int, question: str) -> tuple[dict, list[dict] | None]:
        history = await self._get_history(session_id)
        search_module_executor = make_search_module_executor(session.classroom_id, ai_config.TOP_K_CHUNKS)

        result = await asyncio.to_thread(clarifier_agent.run, question, history, search_module_executor)
        if result["status"] == "practice_requested":
            return await self._start_practice(session_id, student_id, result["practice"], search_module_executor), None
        citations = copy.deepcopy(result.get("sources"))
        await self._attach_source_blocks(session.classroom_id, result.get("sources"))
        return result, citations

    async def _attach_source_blocks(self, classroom_id: int, sources: list[dict] | None) -> None:
        """Tabel dan gambar asli pada chunk sumber modul yang terverifikasi, lengkap dengan deskripsi Annoter, supaya klien menampilkannya di samping jawaban."""
        modul = [s for s in sources or [] if s.get("source_type") == "modul" and s.get("verified") and str(s.get("reference", "")).isdigit()]
        if not modul:
            return
        try:
            blocks = await self.repo.get_visual_blocks_for_references(classroom_id, [int(s["reference"]) for s in modul])
        except Exception:
            logger.warning("blok sumber untuk kelas %s tidak terbaca", classroom_id, exc_info=True)
            return
        for source in modul:
            source["blok"] = [_block_payload(block) for block in blocks.get(int(source["reference"]), [])]

    async def _ensure_no_active_quiz(self, classroom_id: int, student_id: int) -> None:
        """Clarifier tidak boleh dipakai saat siswa sedang mengerjakan kuis (sesi dimulai, belum selesai, dan belum melewati batas waktu)."""
        now = datetime.now(timezone.utc)
        for progress, quiz in await self.repo.get_started_unfinished_quizzes(classroom_id, student_id):
            deadline = min(progress.started_at + timedelta(minutes=quiz.max_duration_minutes), quiz.end_time)
            if now <= deadline:
                raise BadRequestException("Clarifier tidak dapat dipakai saat kuis sedang berlangsung.")

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
        return [{"role": m.role, "content": m.content_markup or m.content} for m in messages]

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
