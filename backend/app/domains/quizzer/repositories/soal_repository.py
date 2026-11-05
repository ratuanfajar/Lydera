from typing import Sequence

from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSession
from app.domains.contents.models import Block
from app.domains.quizzer.models import Soal, SoalJawaban, SoalLangkah, SoalOpsi, SoalStimulus
from app.domains.quizzer.repositories.interfaces.soal_interface import (
    SoalRepositoryInterface,
)
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models.module import Module
from app.domains.quizzer.models.quiz_request import QuizRequest


class SoalRepository(SoalRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]:
        stmt = select(Block).where(Block.chapter_id == chapter_id).order_by(Block.reading_order)
        result = await self.db.scalars(stmt)
        return result.all()

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

    async def update_stimulus_text(
        self, stimulus: SoalStimulus, readable_text: str, source_markup: str = "",
        ringkasan: str | None = None, tabel: dict | None = None, spesifikasi: dict | None = None,
    ) -> None:
        if spesifikasi is not None:
            stimulus.spesifikasi = spesifikasi
        stimulus.readable_text = readable_text
        stimulus.source_markup = source_markup
        stimulus.ringkasan = ringkasan
        stimulus.tabel = tabel
        stimulus.review_status = "edited"

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

    async def get_quiz_questions_with_answers(self, quiz_id: int, student_id: int) -> list[Soal]:
        stmt = (
            select(Soal)
            .where(Soal.quiz_request_id == quiz_id)
            .options(
                selectinload(Soal.stimulus),
                selectinload(Soal.opsi),
                selectinload(Soal.jawaban).selectinload(SoalJawaban.langkah),
            )
            .order_by(Soal.id.asc())
        )
        return list((await self.db.scalars(stmt)).all())

    async def validate_soal_owner(self, soal_id: int, teacher_id: int) -> bool:
        stmt = select(
            exists(
                select(1)
                .select_from(Soal)
                .join(QuizRequest, Soal.quiz_request_id == QuizRequest.id)
                .join(Module, QuizRequest.module_id == Module.id)
                .join(Classroom, Module.classroom_id == Classroom.id)
                .where(Soal.id == soal_id, Classroom.teacher_id == teacher_id)
            )
        )
        return bool(await self.db.scalar(stmt))
