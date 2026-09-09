import asyncio
import traceback
from pathlib import Path


# 1. SETUP PATH TERLEBIH DAHULU SEBELUM IMPORT AI
from app.utils import paths
paths.setup()

# 2. SEKARANG IMPORT AI SERVICES (Otomatis terbaca dari folder sebelah)
import batch
import pipeline
import run_mineru

# 3. IMPORT BACKEND MODULES
import app.core.model_registry
from app.core.db import AsyncSessionLocal
from app.domains.jobs.models import Job
from app.domains.jobs.repositories.interface import JobRepositoryInterface
from app.domains.jobs.repositories.repository import JobRepository
from app.domains.contents.services import ContentService
from app.domains.contents.repositories.repository import ContentRepository

POLL_INTERVAL_SECONDS = 2

async def process_job(job_id: int, pdf_path: str, out_dir: str, chapter_id: int):
    async with AsyncSessionLocal() as db:
        repo: JobRepositoryInterface = JobRepository(db)
        
        job = await db.get(Job, job_id) 
        if not job:
            return

        await repo.update_job_status(job, "running")
        await db.commit()

        try:
            # PENTING: Karena ini Async, jalankan AI (yang sync & berat) di thread!
            def run_heavy_task():
                windows = batch.plan(Path(pdf_path), Path(out_dir), batch.DEFAULT_MAX_PAGES)
                for w in windows:
                    rc = run_mineru.run(pdf_path, w.out_dir, start=w.start_page, end=w.end_page)
                    if rc != 0:
                        raise RuntimeError(f"MinerU gagal pada window {w.label}")
                
                return pipeline.run(out_dir)

            # Jalankan proses MinerU & Pipeline
            list_json_paths = await asyncio.to_thread(run_heavy_task)

            # Ingest JSON hasil Pipeline ke Database pakai DDD
            content_repo = ContentRepository(db)
            content_service = ContentService(content_repo, db)

            total_blocks = 0

            for json_path in list_json_paths:
                blocks_inserted = await content_service.ingest_annotated_json(json_path, chapter_id)
                total_blocks += blocks_inserted

            await repo.update_job_status(job, "done", blocks_total=total_blocks)
            await db.commit()

        except Exception as exc:
            traceback.print_exc()
            await repo.update_job_status(job, "failed", error=str(exc))
            await db.commit()

async def worker_loop():
    print("[INFO] Worker MinerU Async jalan, menunggu job di antrean...")
    
    while True:
        async with AsyncSessionLocal() as db:
            repo: JobRepositoryInterface = JobRepository(db)
            job = await repo.get_next_queued_job()

        if job is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue
        
        await process_job(job.id, job.pdf_path, job.out_dir, job.chapter_id)


if __name__ == "__main__":
    asyncio.run(worker_loop())