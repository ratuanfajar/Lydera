from redis.asyncio import Redis
from app.core.config import settings
from sqlalchemy import and_, func, select, text, update
from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.contents.models.block import Block
from app.domains.contents.models.chapter import Chapter
from app.domains.contents.models.module import Module
from app.domains.jobs.models.job import Job
from app.domains.contents.models.chapter_progress import ChapterProgress
from app.domains.contents.models.module_progress import ModuleProgress


async def enqueue_module_progress_job(module_id: int) -> bool:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = f"lock:recalculate_module:{module_id}"
    pending_key = f"pending:recalculate_module:{module_id}"

    try:
        is_new_job = await redis.set(lock_key, "locked", ex=60, nx=True)
        if not is_new_job:
            await redis.set(pending_key, "true", ex=60)
            return False

        await recalculate_module_progress_task.kiq(module_id=module_id)
        return True
    finally:
        await redis.aclose()



@broker.task
async def recalculate_module_progress_task(module_id: int) -> None:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = f"lock:recalculate_module:{module_id}"
    pending_key = f"pending:recalculate_module:{module_id}"

    async with AsyncSessionLocal() as db:
        try:
            total_chapters_stmt = select(func.count(Chapter.id)).where(Chapter.module_id == module_id)
            total_chapters = (await db.execute(total_chapters_stmt)).scalar() or 0

            if total_chapters == 0:
                calculated_progress = 0.0
            else:
                completed_chapters_stmt = (
                    select(func.count(func.distinct(Chapter.id)))
                    .join(Block, Block.chapter_id == Chapter.id)
                    .where(Chapter.module_id == module_id)
                )
                completed_chapters = (await db.execute(completed_chapters_stmt)).scalar() or 0
                calculated_progress = round((completed_chapters / total_chapters) * 100, 2)

            module = await db.get(Module, module_id)
            if module:
                module.progress = calculated_progress
                await db.commit()

        except Exception as exc:
            await db.rollback()
            raise exc
        finally:
            has_pending = await redis.get(pending_key)
            await redis.delete(lock_key)
            await redis.delete(pending_key)
            await redis.aclose()

            if has_pending:
                await enqueue_module_progress_job(module_id)


async def enqueue_chapter_progress_reset_job(chapter_id: int) -> bool:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = f"lock:reset_chapter_progress:{chapter_id}"
    pending_key = f"pending:reset_chapter_progress:{chapter_id}"

    try:
        # Acquire lock
        is_new_job = await redis.set(lock_key, "locked", ex=60, nx=True)
        if not is_new_job:
            # Task is currently running; flag it so it re-runs after finishing
            await redis.set(pending_key, "true", ex=60)
            return False

        await reset_chapter_progress_task.kiq(chapter_id=chapter_id)
        return True
    finally:
        await redis.aclose()

@broker.task
async def reset_chapter_progress_task(chapter_id: int) -> None:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = f"lock:reset_chapter_progress:{chapter_id}"
    pending_key = f"pending:reset_chapter_progress:{chapter_id}"

    async with AsyncSessionLocal() as db:
        try:
            chapter = await db.get(Chapter, chapter_id)
            if not chapter or not chapter.module_id:
                return

            module_id = chapter.module_id

            # 1. Reset ChapterProgress for all students on this chapter
            await db.execute(
                update(ChapterProgress)
                .where(ChapterProgress.chapter_id == chapter_id)
                .values(is_done=False, completed_at=None)
            )

            # 2. Total chapters in the module
            total_chap_stmt = select(func.count(Chapter.id)).where(Chapter.module_id == module_id)
            total_chapters = (await db.execute(total_chap_stmt)).scalar() or 0

            if total_chapters > 0:
                # Correlated subquery: counts completed chapters for each student in ModuleProgress
                completed_count_subq = (
                    select(func.count(ChapterProgress.id))
                    .join(Chapter, Chapter.id == ChapterProgress.chapter_id)
                    .where(
                        Chapter.module_id == module_id,
                        ChapterProgress.student_id == ModuleProgress.student_id,
                        ChapterProgress.is_done == True,
                    )
                    .scalar_subquery()
                )

                # Pure SQLAlchemy bulk update across all students in this module
                recalc_stmt = (
                    update(ModuleProgress)
                    .where(ModuleProgress.module_id == module_id)
                    .values(
                        progress_percentage=(func.coalesce(completed_count_subq, 0) * 100) / total_chapters,
                        is_done=(func.coalesce(completed_count_subq, 0) == total_chapters),
                    )
                )
                await db.execute(recalc_stmt)

            await db.commit()

        except Exception as exc:
            await db.rollback()
            raise exc
        finally:
            has_pending = await redis.get(pending_key)
            await redis.delete(lock_key)
            await redis.delete(pending_key)
            await redis.aclose()

            if has_pending:
                await enqueue_chapter_progress_reset_job(chapter_id)