import asyncio
import logging
from dataclasses import dataclass, field

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.quizzer.models import Soal, SoalJawaban
from app.domains.quizzer.repositories.interface import QuizRepositoryInterface
from app.utils import paths

paths.setup()

from common.config import LLM_MAX_WORKERS
from evaluaizer import evaluate as evaluaizer_evaluate
from quizzer.segment import span_text

logger = logging.getLogger(__name__)

LOCK_SECONDS = 300
EVALUATION_DEADLINE_SECONDS = LOCK_SECONDS - 30
TRANSIENT_FAILURE_COOLDOWN_SECONDS = 45
PERMANENT_FAILURE_COOLDOWN_SECONDS = 300


@dataclass
class Evaluation:
    failed: set[int] = field(default_factory=set)
    busy: bool = False


class AnswerEvaluator:
    def __init__(self, repo: QuizRepositoryInterface, db: AsyncSession, redis: Redis):
        self.repo = repo
        self.db = db
        self.redis = redis

    async def evaluate(self, quiz_request_id: int, student_id: int) -> Evaluation:
        """Evaluasi jawaban salah yang belum dievaluasi; busy bila proses lain sedang mengevaluasi siswa dan kuis yang sama."""
        lock = self.redis.lock(f"evaluaizer_lock:{quiz_request_id}:{student_id}", timeout=LOCK_SECONDS)
        if not await lock.acquire(blocking=False):
            return Evaluation(busy=True)
        try:
            return Evaluation(failed=await self._evaluate_pending(quiz_request_id, student_id))
        finally:
            await _release(lock)

    async def _evaluate_pending(self, quiz_request_id: int, student_id: int) -> set[int]:
        soal_list = await self.repo.get_soal_for_request(quiz_request_id)
        jawaban_by_soal = {j.soal_id: j for j in await self.repo.get_jawaban_for_request(quiz_request_id, student_id)}
        pending = [
            (soal, jawaban_by_soal[soal.id]) for soal in soal_list
            if soal.id in jawaban_by_soal and needs_evaluation(jawaban_by_soal[soal.id])
        ]
        failed = await self.recent_failures([jawaban.id for _, jawaban in pending])
        ready = [(soal, jawaban) for soal, jawaban in pending if jawaban.id not in failed]
        if not ready:
            return failed

        chapter_blocks: dict[int, list] = {}
        arguments = []
        for soal, jawaban in ready:
            if soal.chapter_id not in chapter_blocks:
                blocks = await self.repo.get_blocks_for_chapter(soal.chapter_id)
                chapter_blocks[soal.chapter_id] = [
                    {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text} for b in blocks
                ]
            arguments.append(_evaluation_arguments(soal, jawaban, chapter_blocks[soal.chapter_id]))
        await self.db.commit()

        gate = asyncio.Semaphore(LLM_MAX_WORKERS)
        outcomes = await asyncio.gather(
            *(asyncio.wait_for(_limited(gate, argument), EVALUATION_DEADLINE_SECONDS) for argument in arguments),
            return_exceptions=True,
        )

        failures = []
        try:
            for (soal, jawaban), outcome in zip(ready, outcomes):
                if isinstance(outcome, BaseException):
                    logger.error("evaluasi jawaban %s gagal", jawaban.id, exc_info=outcome)
                    failed.add(jawaban.id)
                    failures.append((jawaban.id, outcome))
                else:
                    await self.repo.save_evaluation(jawaban, outcome)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        for jawaban_id, error in failures:
            await self._mark_failed(jawaban_id, error)
        return failed

    async def recent_failures(self, jawaban_ids: list[int]) -> set[int]:
        failed = set()
        for jawaban_id in jawaban_ids:
            try:
                if await self.redis.exists(_failure_key(jawaban_id)):
                    failed.add(jawaban_id)
            except RedisError:
                logger.warning("penanda gagal evaluasi %s tidak terbaca", jawaban_id, exc_info=True)
        return failed

    async def _mark_failed(self, jawaban_id: int, error: BaseException) -> None:
        cooldown = PERMANENT_FAILURE_COOLDOWN_SECONDS if isinstance(error, ValueError) else TRANSIENT_FAILURE_COOLDOWN_SECONDS
        try:
            await self.redis.set(_failure_key(jawaban_id), 1, ex=cooldown)
        except RedisError:
            logger.warning("penanda gagal evaluasi %s tidak tersimpan", jawaban_id, exc_info=True)


def needs_evaluation(jawaban: SoalJawaban) -> bool:
    return not jawaban.is_correct and (jawaban.evaluated_at is None or jawaban.justification_points is None)


def _failure_key(jawaban_id: int) -> str:
    return f"evaluaizer_failed:{jawaban_id}"


async def _release(lock) -> None:
    try:
        await lock.release()
    except RedisError:
        logger.warning("kunci evaluasi tidak dapat dilepas (kedaluwarsa atau Redis terputus)", exc_info=True)


async def _limited(gate: asyncio.Semaphore, arguments: tuple) -> dict:
    async with gate:
        return await asyncio.to_thread(evaluaizer_evaluate.evaluate_scratchwork, *arguments)


def _evaluation_arguments(soal: Soal, jawaban: SoalJawaban, blocks: list) -> tuple:
    source = span_text(blocks, soal.source_reading_order_start, soal.source_reading_order_end)
    options = {o.label: o.opsi_text for o in sorted(soal.opsi, key=lambda o: o.label)}
    key_steps = [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)]
    student_steps = [l.teks for l in sorted(jawaban.langkah, key=lambda l: l.urutan)]
    stimulus = soal.stimulus.readable_text if soal.stimulus else ""
    return (
        source, stimulus, soal.question_text, options, soal.correct_option, key_steps, soal.kesimpulan,
        jawaban.selected_option, student_steps,
    )
