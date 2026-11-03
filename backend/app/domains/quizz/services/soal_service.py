import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.domains.quizz.models import Soal
from app.domains.quizz.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizz.schemas.soal_edit_request import SoalEditRequest
from app.utils import paths
paths.setup()
from quiz import quiz_regenerate


class SoalService:
    def __init__(self, repo: SoalRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def get_soal(self, soal_id: int) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        return soal

    async def edit_soal(self, soal_id: int, payload: SoalEditRequest) -> Soal:
        """Edit langsung tanpa LLM. Hanya berlaku untuk soal berdiri sendiri (stimulus_id kosong, biasanya LOTS)."""
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if soal.stimulus_id is not None:
            raise BadRequestException("soal ini punya stimulus, koreksi lewat POST /soal/{id}/regenerate")

        try:
            touched = False
            if payload.question_text is not None:
                soal.question_text = payload.question_text
                touched = True
            if payload.correct_option is not None:
                soal.correct_option = payload.correct_option
                touched = True
            if payload.kesimpulan is not None:
                soal.kesimpulan = payload.kesimpulan
                touched = True
            if payload.options is not None:
                await self.repo.replace_soal_opsi(soal_id, payload.options)
                touched = True
            if payload.langkah is not None:
                await self.repo.replace_soal_langkah(soal_id, payload.langkah)
                touched = True
            if touched:
                soal.review_status = "edited"

            await self.db.commit()
            return await self.repo.get_soal_by_id(soal_id)
        except Exception as e:
            await self.db.rollback()
            raise e

    async def regenerate_cluster(self, soal_id: int, feedback: str) -> list[Soal]:
        """Feedback guru untuk SATU soal memicu edit soal itu (bukan generate ulang dari nol).
        Kalau perbaikannya ternyata perlu sampai ke stimulus, stimulus ikut direvisi dan SEMUA soal
        di cluster di-recheck konsistensinya."""
        target_soal = await self.repo.get_soal_by_id(soal_id)
        if target_soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if target_soal.stimulus_id is None:
            raise BadRequestException("soal ini tidak punya stimulus, edit langsung lewat PATCH /soal/{id}")

        stimulus = await self.repo.get_stimulus_by_id(target_soal.stimulus_id)
        cluster = await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        sibling_soal = [s for s in cluster if s.id != soal_id]

        all_blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        blocks_as_rows = [
            {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
            for b in all_blocks
        ]

        def to_dict(s: Soal) -> dict:
            return {
                "id": s.id,
                "question_text": s.question_text,
                "options": {o.label: o.opsi_text for o in s.opsi},
                "correct_option": s.correct_option,
                "langkah": [l.teks for l in sorted(s.langkah, key=lambda l: l.urutan)],
                "kesimpulan": s.kesimpulan,
            }

        try:
            result = await asyncio.to_thread(
                quiz_regenerate.compute_regeneration,
                stimulus.chapter_id, blocks_as_rows,
                stimulus.source_reading_order_start, stimulus.source_reading_order_end,
                stimulus.readable_text, to_dict(target_soal), [to_dict(s) for s in sibling_soal], feedback,
            )
        except Exception as exc:
            raise BadRequestException(f"regenerasi gagal, coba lagi: {exc}")

        try:
            if result["new_stimulus_text"]:
                await self.repo.update_stimulus_text(stimulus, result["new_stimulus_text"])

            for sid, data, val in result["soal_updates"]:
                soal = await self.repo.get_soal_by_id(sid)
                soal.question_text = data["question_text"]
                soal.correct_option = data["correct_option"]
                soal.kesimpulan = data["kesimpulan"]
                soal.review_status = "pending"
                soal.review_priority = "normal" if val["matches"] else "high"
                soal.validation_notes = None
                if not val["matches"]:
                    soal.validation_notes = (
                        f"Validasi independen sampai ke jawaban {val['derived_option']}, berbeda dari "
                        f"jawaban Generation ({data['correct_option']})."
                    )
                await self.repo.replace_soal_opsi(sid, data["options"])
                await self.repo.replace_soal_langkah(sid, data["langkah"])

            await self.db.commit()
            return await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        except Exception as e:
            await self.db.rollback()
            raise e
