import traceback

from app.core.taskiq import broker
from app.core.db import AsyncSessionLocal
from app.domains.chatbot.repositories.repository import ChatbotRepository
from app.domains.chatbot.services import ChatbotService


@broker.task
async def reindex_chapter_task(chapter_id: int) -> None:
    """Reindex embedding satu bab (chunk -> embed -> upsert `block_embeddings`/`chapter_kb`),
    dijalankan async lewat taskiq mirip `process_quiz_request_task` -- dipanggil setelah guru
    publish/edit modul, supaya request publish tidak menunggu batch call embedding API selesai."""
    async with AsyncSessionLocal() as db:
        repo = ChatbotRepository(db)
        service = ChatbotService(repo, db)
        try:
            await service.reindex_chapter(chapter_id)
        except Exception:
            traceback.print_exc()
            await db.rollback()


@broker.task
async def reindex_classroom_task(classroom_id: int) -> None:
    """Reindex SEMUA chapter published di satu classroom -- dipanggil sekali oleh guru supaya
    tidak perlu reindex chapter satu-satu manual. Tiap chapter tetap diproses lewat
    `reindex_chapter_task` masing-masing (bukan satu batch besar), supaya satu chapter gagal
    tidak menggagalkan yang lain, dan bisa jalan paralel di worker."""
    async with AsyncSessionLocal() as db:
        repo = ChatbotRepository(db)
        chapter_ids = await repo.get_chapter_ids_for_classroom(classroom_id)

    for chapter_id in chapter_ids:
        await reindex_chapter_task.kiq(chapter_id=chapter_id)
