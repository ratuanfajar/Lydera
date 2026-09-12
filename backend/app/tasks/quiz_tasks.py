import asyncio
import traceback

from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.quizz.repositories.repository import QuizRepository

from app.utils import paths
paths.setup()

import quiz_pipeline


@broker.task
async def process_quiz_request_task(quiz_request_id: int) -> None:
    """Jalankan Chain 0-4 (`ai-services/quiz/quiz_pipeline.py`) untuk tiap bab yang diminta dalam satu
    quiz_request, simpan hasilnya, lalu perbarui status. Dipanggil async lewat taskiq, mirip pola
    `process_mineru_job_task` di `mineru_tasks.py`."""
    async with AsyncSessionLocal() as db:
        repo = QuizRepository(db)

        quiz_request = await repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            return

        await repo.update_quiz_request_status(quiz_request, "running")
        await db.commit()

        try:
            chapter_links = await repo.get_chapter_links(quiz_request_id)
            for link in chapter_links:
                blocks = await repo.get_blocks_for_chapter(link.chapter_id)
                blocks_as_rows = [
                    {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
                    for b in blocks
                ]
                computed = await asyncio.to_thread(
                    quiz_pipeline.compute_for_chapter,
                    link.chapter_id, blocks_as_rows, link.hots_count, link.lots_count,
                )
                for data, result in computed:
                    review_priority = "normal" if result["matches"] else "high"
                    validation_notes = None
                    if not result["matches"]:
                        validation_notes = (
                            f"Validasi independen sampai ke jawaban {result['derived_option']}, berbeda dari "
                            f"jawaban Generation ({data['correct_option']}). Langkah validasi: "
                            f"{'; '.join(result['derived_langkah'])}"
                        )
                    await repo.save_soal(quiz_request_id, link.chapter_id, data, review_priority, validation_notes)

            quiz_request = await repo.get_quiz_request(quiz_request_id)
            await repo.update_quiz_request_status(quiz_request, "done")
            await db.commit()
        except Exception as exc:
            traceback.print_exc()
            await db.rollback()
            quiz_request = await repo.get_quiz_request(quiz_request_id)
            await repo.update_quiz_request_status(quiz_request, "failed", error=str(exc))
            await db.commit()
