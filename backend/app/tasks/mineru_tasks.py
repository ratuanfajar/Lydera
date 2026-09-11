import asyncio
import json
import traceback
from pathlib import Path
from redis.asyncio import Redis
import app.core.model_registry
from app.utils import paths
paths.setup()

import batch
import pipeline
import run_mineru

from app.core.taskiq import broker
from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.domains.jobs.models import Job
from app.domains.jobs.repositories.repository import JobRepository
from app.domains.contents.repositories.repository import ContentRepository
from app.domains.contents.services import ContentService

MAX_RETRIES = 3

_last_progress_map: dict[int, int] = {}

async def publish_progress(redis: Redis, job_id: int, status: str, progress:int, message: str):
    """Helper to publish real-time progress events to Redis Pub/Sub with monotonic progress safeguard."""
    global _last_progress_map

    if status == "retrying":
        _last_progress_map[job_id] = 0
    else:
        last_p = _last_progress_map.get(job_id, 0)
        if progress < last_p:
            progress = last_p
        else:
            _last_progress_map[job_id] = progress

    payload = json.dumps({
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message
    })

    await redis.publish(f"job_progress:{job_id}", payload)

@broker.task
async def process_mineru_job_task(job_id:int, pdf_path:str, out_dir:str, chapter_id:int, attempt: int = 1) -> None:
    redis = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_keepalive=True
    )

    async with AsyncSessionLocal() as db:
        repo = JobRepository(db)
        job = await db.get(Job, job_id)
        if not job:
            await redis.aclose()
            return

        await repo.update_job_status(job, "running")
        await db.commit()
        await publish_progress(redis, job_id, "running", 5, "Job Started.Initializing MinerU extraction...")

        try:
            # All in One
            # 1. Real-time progress callback for MinerU execution
            # async def report_progress(percent: int, message: str):
            #     await publish_progress(redis, job_id, "running", percent, message)

            # rc = await run_mineru.run_async(
            #     pdf=pdf_path,
            #     out=out_dir,
            #     progress_callback=report_progress
            # )
            # if rc != 0:
            #     raise RuntimeError(f"MinerU extraction failed with return code {rc}")

            windows = batch.plan(Path(pdf_path), Path(out_dir), batch.DEFAULT_MAX_PAGES)
            total_windows = len(windows)

            # Batch using run
            for idx, w in enumerate(windows):
                # Execute blocking run() in a separate thread pool
                rc = await asyncio.to_thread(
                    run_mineru.run,
                    pdf=pdf_path,
                    out=w.out_dir,
                    start=w.start_page,
                    end=w.end_page
                )

                if rc != 0:
                    raise RuntimeError(f"MinerU extraction failed on batch window {w.label} (code {rc})")

            # Publish progress step AFTER each batch completes
                window_span = 70.0 / total_windows
                overall_progress = 5 + int((idx + 1) * window_span)
                await publish_progress(
                    redis, 
                    job_id, 
                    "running", 
                    overall_progress, 
                    f"Completed batch {idx + 1}/{total_windows} (Pages {w.start_page}–{w.end_page})"
                )
    
            # 2. Run Pipeline aggregation
            await publish_progress(redis, job_id, "running", 75, "Aggregating extracted output...")
            list_json_paths = await asyncio.to_thread(pipeline.run, out_dir)

            # 3. Database Ingestion
            await publish_progress(redis, job_id, "running", 85, "Ingesting extracted content to database...")
            content_repo = ContentRepository(db)
            content_service = ContentService(content_repo, db)

            total_blocks = 0
            for json_path in list_json_paths:
                blocks_inserted = await content_service.ingest_annotated_json(json_path, chapter_id)
                total_blocks += blocks_inserted

            # 4. Success
            await repo.update_job_status(job, "done", blocks_total=total_blocks)
            await db.commit()
            await publish_progress(redis, job_id, "done", 100, f"Successfully processed {total_blocks} blocks.")

                
        except Exception as exc:
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                await repo.update_job_status(job, "retrying")
                await db.commit()
                await publish_progress(redis, job_id, "retrying", 0, f"Error occurred. Retrying attempt {attempt + 1}/{MAX_RETRIES}...")
                await process_mineru_job_task.kiq(
                    job_id=job_id,
                    pdf_path=pdf_path,
                    out_dir=out_dir,
                    chapter_id=chapter_id,
                    attempt=attempt + 1
                )
            else:
                await repo.update_job_status(job, "failed", error=str(exc))
                await db.commit()
                await publish_progress(redis, job_id, "failed", 0, f"Final Failure: {str(exc)}")
        finally:
            await redis.aclose()
