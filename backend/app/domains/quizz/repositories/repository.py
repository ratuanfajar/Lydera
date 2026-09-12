from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSession
from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalLangkah, SoalOpsi, SoalStimulus
from app.domains.quizz.repositories.interface import QuizRepositoryInterface


class QuizRepository(QuizRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    # Module/Chapter
    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)

    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None:
        return await self.db.get(Chapter, chapter_id)

    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]:
        stmt = select(Block).where(Block.chapter_id == chapter_id).order_by(Block.reading_order)
        result = await self.db.scalars(stmt)
        return result.all()

    # QuizRequest
    async def create_quiz_request(self, module_id: int) -> int:
        new_request = QuizRequest(module_id=module_id, status="queued")
        self.db.add(new_request)
        await self.db.flush()
        return new_request.id

    async def link_chapter(self, quiz_request_id: int, chapter_id: int, hots_count: int, lots_count: int) -> None:
        self.db.add(QuizRequestChapter(
            quiz_request_id=quiz_request_id,
            chapter_id=chapter_id,
            hots_count=hots_count,
            lots_count=lots_count,
        ))
        await self.db.flush()

    async def get_quiz_request(self, quiz_request_id: int) -> QuizRequest | None:
        return await self.db.get(QuizRequest, quiz_request_id)

    async def get_chapter_links(self, quiz_request_id: int) -> Sequence[QuizRequestChapter]:
        stmt = select(QuizRequestChapter).where(QuizRequestChapter.quiz_request_id == quiz_request_id)
        result = await self.db.scalars(stmt)
        return result.all()

    async def update_quiz_request_status(self, quiz_request: QuizRequest, status: str, error: str | None = None) -> None:
        quiz_request.status = status
        if error is not None:
            quiz_request.error = error

    # Soal
    async def save_soal(self, quiz_request_id: int, chapter_id: int, data: dict,
                         review_priority: str, validation_notes: str | None) -> int:
        stimulus_id = None
        stimulus = data.get("stimulus")
        if stimulus:
            new_stimulus = SoalStimulus(
                quiz_request_id=quiz_request_id,
                chapter_id=chapter_id,
                source_markup=stimulus.get("source_markup", ""),
                readable_text=stimulus["readable_text"],
                source_reading_order_start=data["reading_order_start"],
                source_reading_order_end=data["reading_order_end"],
            )
            self.db.add(new_stimulus)
            await self.db.flush()
            stimulus_id = new_stimulus.id

        new_soal = Soal(
            quiz_request_id=quiz_request_id,
            chapter_id=chapter_id,
            stimulus_id=stimulus_id,
            bloom_level=data["bloom_level"],
            question_text=data["question_text"],
            correct_option=data["correct_option"],
            kesimpulan=data["kesimpulan"],
            source_reading_order_start=data["reading_order_start"],
            source_reading_order_end=data["reading_order_end"],
            review_priority=review_priority,
            validation_notes=validation_notes,
        )
        self.db.add(new_soal)
        await self.db.flush()

        for label, opsi_text in data["options"].items():
            self.db.add(SoalOpsi(soal_id=new_soal.id, label=label, opsi_text=opsi_text))
        for urutan, teks in enumerate(data["langkah"], start=1):
            self.db.add(SoalLangkah(soal_id=new_soal.id, urutan=urutan, teks=teks))
        await self.db.flush()

        return new_soal.id

    async def get_soal_by_id(self, soal_id: int) -> Soal | None:
        stmt = (
            select(Soal)
            .where(Soal.id == soal_id)
            .options(selectinload(Soal.opsi), selectinload(Soal.langkah), selectinload(Soal.stimulus))
        )
        result = await self.db.scalars(stmt)
        return result.first()

    async def get_soal_for_request(self, quiz_request_id: int) -> Sequence[Soal]:
        stmt = (
            select(Soal)
            .where(Soal.quiz_request_id == quiz_request_id)
            .options(selectinload(Soal.opsi), selectinload(Soal.langkah), selectinload(Soal.stimulus))
            .order_by(Soal.id)
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_stimulus_by_id(self, stimulus_id: int) -> SoalStimulus | None:
        return await self.db.get(SoalStimulus, stimulus_id)

    async def get_soal_by_stimulus(self, stimulus_id: int) -> Sequence[Soal]:
        stmt = (
            select(Soal)
            .where(Soal.stimulus_id == stimulus_id)
            .options(selectinload(Soal.opsi), selectinload(Soal.langkah), selectinload(Soal.stimulus))
            .order_by(Soal.id)
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def update_stimulus_text(self, stimulus: SoalStimulus, readable_text: str) -> None:
        stimulus.readable_text = readable_text
        stimulus.review_status = "edited"

    async def set_review_status(self, soal: Soal, status: str) -> None:
        soal.review_status = status

    async def replace_soal_opsi(self, soal_id: int, options: dict[str, str]) -> None:
        # Manipulasi lewat koleksi relationship (soal.opsi), bukan session.delete() langsung --
        # Soal.opsi punya cascade="all, delete-orphan", jadi clear()+append() di sini yang membuat
        # SQLAlchemy men-track hapus/tambah baris dengan benar. session.delete() langsung ke child
        # tidak memperbarui koleksi relationship yang sudah ter-load di identity map, sehingga
        # pembacaan berikutnya lewat get_soal_by_id() bisa mengembalikan data lama (stale).
        soal = await self.get_soal_by_id(soal_id)
        soal.opsi.clear()
        await self.db.flush()
        for label, opsi_text in options.items():
            soal.opsi.append(SoalOpsi(soal_id=soal_id, label=label, opsi_text=opsi_text))
        await self.db.flush()

    async def replace_soal_langkah(self, soal_id: int, langkah: list[str]) -> None:
        soal = await self.get_soal_by_id(soal_id)
        soal.langkah.clear()
        await self.db.flush()
        for urutan, teks in enumerate(langkah, start=1):
            soal.langkah.append(SoalLangkah(soal_id=soal_id, urutan=urutan, teks=teks))
        await self.db.flush()
