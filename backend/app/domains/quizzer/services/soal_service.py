import asyncio
import logging
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.quizzer.models import Soal
from app.domains.quizzer.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizzer.schemas.soal_edit_request import SoalEditRequest, StimulusEditRequest
from app.utils import paths
from app.domains.quizzer.models.soal_stimulus import SoalStimulus
from app.domains.quizzer.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
paths.setup()
from app.domains.quizzer.models.quiz_request import QuizRequestStatus
from common import math_text
from quizzer import quizzer_regenerate
from quizzer import readable as quizzer_readable
from quizzer import segment as quizzer_segment

logger = logging.getLogger(__name__)

def _review_dict(soal: Soal) -> dict:
    """Bentuk yang diverifikasi: teks siap-baca (yang didengar siswa) plus markup untuk audit kesetiaan."""
    return {
        "id": soal.id,
        "question_text": soal.question_text,
        "options": {o.label: o.opsi_text for o in soal.opsi},
        "correct_option": soal.correct_option,
        "langkah": [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": soal.kesimpulan,
        "markup": soal.markup,
        "stimulus": _stimulus_dict(soal.stimulus) if soal.stimulus else None,
    }

def _stimulus_dict(stimulus: SoalStimulus) -> dict:
    result = {"readable_text": stimulus.readable_text, "source_markup": stimulus.source_markup or ""}
    if stimulus.jenis != "teks" and stimulus.spesifikasi:
        result.update(jenis=stimulus.jenis, spesifikasi=stimulus.spesifikasi)
    return result

def _soal_to_dict(soal: Soal) -> dict:
    """Bentuk teks yang diedit LLM: markup bila soal punya rumus, selain itu teks biasa."""
    markup = soal.markup or {}
    return {
        "id": soal.id,
        "question_text": markup.get("question", soal.question_text),
        "options": markup.get("options") or {o.label: o.opsi_text for o in soal.opsi},
        "correct_option": soal.correct_option,
        "langkah": markup.get("langkah") or [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": markup.get("kesimpulan", soal.kesimpulan),
    }

    
def _review_flags(self, issues: list[str]) -> tuple[str, str | None]:
    return ("high" if issues else "normal"), ("\n".join(issues) or None)


def _readable_dict(soal: Soal) -> dict:
    return {
        "question": soal.question_text,
        "options": {o.label: o.opsi_text for o in soal.opsi},
        "langkah": [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)],
        "kesimpulan": soal.kesimpulan,
    }

def _sent_texts(payload) -> list[str]:
    texts: list[str] = []
    for source in (payload, SimpleNamespace(**(payload.markup or {}))):
        for value in (getattr(source, "question_text", None), getattr(source, "question", None), getattr(source, "kesimpulan", None)):
            texts.append(value or "")
        for key in ("options", "langkah"):
            value = getattr(source, key, None)
            texts.extend((value.values() if isinstance(value, dict) else value) or [])
    return texts

class SoalService:
    def __init__(self,quiz_repo: QuizRequestRepositoryInterface, repo: SoalRepositoryInterface, db: AsyncSession):
        self.quiz_repo = quiz_repo
        self.repo = repo
        self.db = db

    async def get_soal(self, soal_id: int) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        return soal

    async def edit_soal(self, soal_id: int, teacher_id: int, payload: SoalEditRequest) -> Soal:
        """Edit langsung isi soal (LOTS maupun HOTS); sesudah simpan, validator memverifikasi ulang. Stimulus HOTS diedit lewat edit_stimulus."""
        await self._ensure_soal_owner(soal_id, teacher_id)
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        await self._ensure_quiz_editable(soal.quiz_request_id)

        if soal.stimulus_id is not None:
            raise BadRequestException("soal ini punya stimulus, koreksi lewat POST /soal/{id}/regenerate")

        touched = False
        try:
            text_fields = {
                "question": payload.question_text, "options": payload.options,
                "langkah": payload.langkah, "kesimpulan": payload.kesimpulan,
            }
            if payload.markup or any(value is not None for value in text_fields.values()):
                merged = {**_readable_dict(soal), **(soal.markup or {})}
                merged.update({key: value for key, value in text_fields.items() if value is not None})
                merged.update(payload.markup or {})
                problems = quizzer_readable.fields_issues(merged) or math_text.plain_text_issues(_sent_texts(payload))
                if problems:
                    raise BadRequestException("Markup tidak valid: " + "; ".join(problems))
                try:
                    readable, markup = await asyncio.to_thread(quizzer_readable.derive_fields, merged)
                except Exception:
                    logger.exception("verbalisasi markup soal %s gagal", soal_id)
                    raise BadRequestException("Teks siap-baca tidak dapat dibuat dari markup ini, coba lagi.")
                soal.question_text = readable["question"]
                soal.kesimpulan = readable["kesimpulan"]
                soal.markup = markup
                await self.repo.replace_soal_opsi(soal_id, readable["options"])
                await self.repo.replace_soal_langkah(soal_id, readable["langkah"])
                touched = True
            if payload.correct_option is not None:
                soal.correct_option = payload.correct_option
                touched = True
            if touched:
                soal.review_status = "edited"

            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

        updated = await self.repo.get_soal_by_id(soal_id)
        if touched:
            await self._refresh_review_flags(updated)
            updated = await self.repo.get_soal_by_id(soal_id)
        return updated

    async def edit_stimulus(self, soal_id: int, teacher_id: int, payload: StimulusEditRequest) -> list[Soal]:
        """Edit langsung stimulus pada bentuk aslinya; bacaan diturunkan ulang dan seluruh soal di cluster diverifikasi ulang. Tidak ada yang disimpan bila editan tidak valid."""
        await self._ensure_soal_owner(soal_id, teacher_id)
        target = await self.repo.get_soal_by_id(soal_id)
        if target is None:
            raise NotFoundException("soal tidak ditemukan")
        if target.stimulus_id is None:
            raise BadRequestException("soal ini tidak punya stimulus")
        await self._ensure_quiz_editable(target.quiz_request_id)
        stimulus = await self.repo.get_stimulus_by_id(target.stimulus_id)
        if stimulus is None:
            raise NotFoundException("stimulus tidak ditemukan")
        typed = stimulus.jenis != "teks" and bool(stimulus.spesifikasi)
        if typed and payload.spesifikasi is None:
            raise BadRequestException("stimulus ini bertipe; kirim spesifikasi")
        if not typed and payload.source_markup is None:
            raise BadRequestException("stimulus ini teks; kirim source_markup")

        cluster = list(await self.repo.get_soal_by_stimulus(stimulus.id))
        blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        rows = [{"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text} for b in blocks]
        current = {
            "jenis": stimulus.jenis, "spesifikasi": stimulus.spesifikasi,
            "readable_text": stimulus.readable_text, "source_markup": stimulus.source_markup or "",
        }
        edit = {"narasi": payload.narasi, "spesifikasi": payload.spesifikasi} if typed else {"source_markup": payload.source_markup}
        try:
            result = await asyncio.to_thread(
                quizzer_regenerate.compute_stimulus_edit,
                rows, target.source_reading_order_start, target.source_reading_order_end,
                current, [_review_dict(s) for s in cluster], edit,
            )
        except ValueError as exc:
            raise BadRequestException(str(exc))
        except Exception:
            logger.exception("edit stimulus soal %s gagal", soal_id)
            raise BadRequestException("Edit stimulus gagal, coba lagi.")

        try:
            new = result["new_stimulus"]
            await self.repo.update_stimulus_text(
                stimulus, new["readable_text"], new["source_markup"], new["ringkasan"], new["tabel"], new.get("spesifikasi"),
            )
            for soal in cluster:
                soal.review_status = "edited"
                soal.review_priority, soal.validation_notes = _review_flags(result["soal_issues"].get(soal.id, []))
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return list(await self.repo.get_soal_by_stimulus(stimulus.id))

    
    async def regenerate_cluster(self, soal_id: int, teacher_id: int, feedback: str) -> list[Soal]:
        """Feedback guru untuk SATU soal memicu edit soal itu (bukan generate ulang dari nol --
        lihat `ai-services/quizzer/revise.py`). Kalau perbaikannya ternyata perlu sampai ke stimulus
        (shared ke soal lain di cluster), stimulus ikut direvisi dan SEMUA soal di cluster
        di-recheck konsistensinya -- kalau tidak, cuma soal yang dikritik yang tersentuh, stimulus
        dan soal lain di cluster tetap utuh. Guru approve draft hasilnya sebelum final --
        review_status dikembalikan ke 'pending', bukan otomatis final."""
        await self._ensure_soal_owner(soal_id, teacher_id)
        target_soal = await self.repo.get_soal_by_id(soal_id)
        if target_soal is None:
            raise NotFoundException("soal tidak ditemukan")
        if target_soal.stimulus_id is None:
            raise BadRequestException("soal ini tidak punya stimulus, edit langsung lewat PATCH /soal/{id}")
        await self._ensure_quiz_editable(target_soal.quiz_request_id)

        stimulus = await self.repo.get_stimulus_by_id(target_soal.stimulus_id)
        cluster = await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        sibling_soal = [s for s in cluster if s.id != soal_id]

        all_blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        blocks_as_rows = [
            {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
            for b in all_blocks
        ]

        try:
            print(f'Block As Rows :{len(blocks_as_rows)}')
            print(f'Source Reading Order Start :{target_soal.source_reading_order_start}')
            print(f'Source Reading Order End :{target_soal.source_reading_order_end}')
            print(f'Stimulus Source Markup :{stimulus.source_markup}')
            print(f'Stimulus Readble text:{stimulus.readable_text}')
            print(f'Soal to Dict :{_soal_to_dict(target_soal)}')
            print(f'Feedback :{feedback}')
            print(f'Stimulus Jenis :{stimulus.jenis}')
            print(f'Stimulus Spesifikasi :{stimulus.spesifikasi}')

            result = await asyncio.to_thread(
                quizzer_regenerate.compute_regeneration,
                blocks_as_rows,
                target_soal.source_reading_order_start, 
                target_soal.source_reading_order_end,
                stimulus.source_markup or "",
                stimulus.readable_text, 
                _soal_to_dict(target_soal),
                [_soal_to_dict(s) for s in sibling_soal],
                feedback,
                stimulus.jenis, stimulus.spesifikasi,
            )
            print(f'Result :{result}')
        except Exception:
            logger.exception("regenerasi soal %s gagal", soal_id)
            raise BadRequestException("Regenerasi gagal, coba lagi.")

        try:
            if result["new_stimulus"]:
                await self.repo.update_stimulus_text(
                    stimulus, result["new_stimulus"]["readable_text"], result["new_stimulus"]["source_markup"],
                    result["new_stimulus"]["ringkasan"], result["new_stimulus"]["tabel"],
                    result["new_stimulus"].get("spesifikasi"),
                )

            for sid, data, issues in result["soal_updates"]:
                soal = await self.repo.get_soal_by_id(sid)
                soal.question_text = data["question_text"]
                soal.markup = data.get("markup")
                soal.correct_option = data["correct_option"]
                soal.kesimpulan = data["kesimpulan"]
                soal.review_status = "pending"
                print(f'Issue : {issues}')
                soal.review_priority, soal.validation_notes = _review_flags(issues)
                await self.repo.replace_soal_opsi(sid, data["options"])
                await self.repo.replace_soal_langkah(sid, data["langkah"])

            await self.db.commit()
            return await self.repo.get_soal_by_stimulus(target_soal.stimulus_id)
        except Exception as e:
            await self.db.rollback()
            raise e

    async def _ensure_soal_owner(self, soal_id: int, teacher_id: int) -> None:
        if not await self.repo.validate_soal_owner(soal_id, teacher_id):
            raise ForbiddenException("Soal tidak ditemukan atau Anda tidak memiliki akses.")

    async def _ensure_quiz_editable(self, quiz_request_id: int) -> None:
        """Kunci jawaban terkunci begitu kuis dipublikasikan atau sudah dikerjakan siswa; hanya kuis draft tanpa pengerjaan yang boleh diubah."""
        quiz = await self.quiz_repo.get_quiz_request(quiz_request_id)
        if quiz is not None and quiz.status_published == QuizRequestStatus.PUBLISH:
            raise BadRequestException("Kuis sudah dipublikasikan; kembalikan ke draft untuk mengubah soal.")
        if await self.quiz_repo.has_quiz_progress(quiz_request_id):
            raise BadRequestException("Kuis sudah dikerjakan siswa; soal tidak dapat diubah lagi.")

    async def _refresh_review_flags(self, soal: Soal) -> None:
        """Verifikasi ulang soal yang diedit guru (jawab buta + audit) lalu perbarui tanda review; tidak pernah menggagalkan simpan."""
        try:
            blocks = await self.repo.get_blocks_for_chapter(soal.chapter_id)
            rows = [{"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text} for b in blocks]
            source_text = quizzer_segment.span_text(rows, soal.source_reading_order_start, soal.source_reading_order_end)
            stimulus_text = soal.stimulus.readable_text if soal.stimulus else ""
            issues = await asyncio.to_thread(quizzer_regenerate.review_soal, source_text, _review_dict(soal), stimulus_text)
        except Exception:
            logger.exception("verifikasi ulang soal %s gagal", soal.id)
            issues = ["Verifikasi otomatis gagal dijalankan; periksa soal ini secara manual."]
        soal.review_priority, soal.validation_notes = _review_flags(issues)
        await self.db.commit()




