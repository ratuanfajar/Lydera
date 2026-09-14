import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.domains.quizz.models import Soal, SoalJawaban
from app.domains.quizz.repositories.interface import QuizRepositoryInterface
from app.domains.quizz.schemas import QuizResultItem, SoalJustification, SoalSubmitRequest

import paths

paths.setup()

import evaluate as quiz_evaluate
import regenerate as quiz_regenerate
from segment import Segment


class QuizService:
    def __init__(self, repo: QuizRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    # -- Write (dengan commit) --
    async def create_quiz_request(self, module_id: int, chapters: list) -> int:
        """Validasi module/chapter, buat quiz_request + link tiap bab dengan target soal-nya sendiri.
        Pemrosesan sesungguhnya (generate + validate) dijalankan async lewat quiz_tasks.py."""
        if not chapters:
            raise BadRequestException("chapters tidak boleh kosong")

        module = await self.repo.get_module_by_id(module_id)
        if module is None:
            raise NotFoundException("modul tidak ditemukan")

        for item in chapters:
            chapter = await self.repo.get_chapter_by_id(item.chapter_id)
            if chapter is None:
                raise NotFoundException(f"chapter_id={item.chapter_id} tidak ditemukan")
            if chapter.module_id != module_id:
                raise BadRequestException(f"chapter_id={item.chapter_id} bukan bagian dari modul ini")

        try:
            quiz_request_id = await self.repo.create_quiz_request(module_id)
            for item in chapters:
                await self.repo.link_chapter(quiz_request_id, item.chapter_id, item.hots_count, item.lots_count)
            await self.db.commit()
            return quiz_request_id
        except Exception as e:
            await self.db.rollback()
            raise e

    async def edit_soal(self, soal_id: int, payload) -> Soal:
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

    async def set_review_status(self, soal_id: int, status: str) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        try:
            await self.repo.set_review_status(soal, status)
            await self.db.commit()
            return soal
        except Exception as e:
            await self.db.rollback()
            raise e

    async def regenerate_cluster(self, stimulus_id: int, feedback: str) -> list[Soal]:
        """Feedback guru memicu LLM meregenerasi satu cluster HOTS penuh (stimulus + semua soal yang
        berbagi stimulus itu). Guru approve draft hasilnya sebelum final -- review_status dikembalikan
        ke 'pending', bukan otomatis final."""
        stimulus = await self.repo.get_stimulus_by_id(stimulus_id)
        if stimulus is None:
            raise NotFoundException(f"stimulus_id={stimulus_id} tidak ditemukan")

        cluster = await self.repo.get_soal_by_stimulus(stimulus_id)
        if not cluster:
            raise NotFoundException(f"tidak ada soal untuk stimulus_id={stimulus_id}")

        all_blocks = await self.repo.get_blocks_for_chapter(stimulus.chapter_id)
        blocks_as_rows = [
            {"reading_order": b.reading_order, "block_type": b.block_type, "readable_text": b.readable_text}
            for b in all_blocks
        ]
        soal_bloom_levels = [(soal.id, soal.bloom_level) for soal in cluster]

        try:
            results = await asyncio.to_thread(
                quiz_regenerate.compute_cluster,
                stimulus.chapter_id, blocks_as_rows,
                stimulus.source_reading_order_start, stimulus.source_reading_order_end,
                soal_bloom_levels, feedback,
            )
        except Exception as exc:
            raise BadRequestException(f"regenerasi gagal, coba lagi: {exc}")

        try:
            new_stimulus_text = (results[0][1].get("stimulus") or {}).get("readable_text", "")
            if new_stimulus_text:
                await self.repo.update_stimulus_text(stimulus, new_stimulus_text)

            for soal_id, data, val in results:
                soal = await self.repo.get_soal_by_id(soal_id)
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
                await self.repo.replace_soal_opsi(soal_id, data["options"])
                await self.repo.replace_soal_langkah(soal_id, data["langkah"])

            await self.db.commit()
            return await self.repo.get_soal_by_stimulus(stimulus_id)
        except Exception as e:
            await self.db.rollback()
            raise e

    # -- Read (tanpa commit) --
    async def get_quiz_request_status(self, quiz_request_id: int):
        quiz_request = await self.repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("quiz_request tidak ditemukan")
        return quiz_request

    async def list_soal_for_request(self, quiz_request_id: int) -> list[Soal]:
        return await self.repo.get_soal_for_request(quiz_request_id)

    async def get_soal(self, soal_id: int) -> Soal:
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")
        return soal

    # -- Jawaban siswa --
    async def submit_answer(self, soal_id: int, student_id: int, payload: SoalSubmitRequest) -> None:
        """Simpan jawaban + langkah pengerjaan siswa untuk satu soal. Tidak ada panggilan LLM di
        sini -- evaluasi (untuk yang salah) baru dijalankan saat siswa minta hasil akhir kuis lewat
        `get_quiz_results`. Satu siswa cuma bisa submit sekali per soal (unique constraint DB)."""
        soal = await self.repo.get_soal_by_id(soal_id)
        if soal is None:
            raise NotFoundException("soal tidak ditemukan")

        existing = await self.repo.get_soal_jawaban(soal_id, student_id)
        if existing is not None:
            raise BadRequestException("soal ini sudah dijawab")

        is_correct = payload.selected_option == soal.correct_option
        try:
            await self.repo.create_soal_jawaban(soal_id, student_id, payload.selected_option, is_correct, payload.langkah)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

    async def get_quiz_results(self, quiz_request_id: int, student_id: int) -> list[QuizResultItem]:
        """Hasil kuis siswa untuk satu quiz_request: tiap soal yang dijawab SALAH dan belum pernah
        dievaluasi dipicu evaluasinya sekarang (paralel), lalu hasilnya disimpan supaya panggilan
        berikutnya tidak memanggil LLM ulang (`evaluated_at` jadi penanda sudah final)."""
        quiz_request = await self.repo.get_quiz_request(quiz_request_id)
        if quiz_request is None:
            raise NotFoundException("quiz_request tidak ditemukan")

        soal_list = await self.repo.get_soal_for_request(quiz_request_id)
        jawaban_list = await self.repo.get_jawaban_for_request(quiz_request_id, student_id)
        jawaban_by_soal = {j.soal_id: j for j in jawaban_list}

        to_evaluate: list[tuple[Soal, SoalJawaban]] = []
        for soal in soal_list:
            jawaban = jawaban_by_soal.get(soal.id)
            if jawaban is not None and not jawaban.is_correct and jawaban.evaluated_at is None:
                to_evaluate.append((soal, jawaban))

        if to_evaluate:
            evaluations = await asyncio.gather(*[
                self._evaluate_one(soal, jawaban) for soal, jawaban in to_evaluate
            ])
            try:
                for (_, jawaban), result in zip(to_evaluate, evaluations):
                    await self.repo.save_evaluation(
                        jawaban, result.get("divergence_step"),
                        result.get("diagnosis", ""), result.get("personalized_justification", ""),
                    )
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                raise e

        results = []
        for soal in soal_list:
            jawaban = jawaban_by_soal.get(soal.id)
            justification = None
            if jawaban is not None and not jawaban.is_correct:
                justification = SoalJustification(
                    divergence_step=jawaban.divergence_step,
                    diagnosis=jawaban.diagnosis or "",
                    personalized_justification=jawaban.personalized_justification or "",
                )
            results.append(QuizResultItem(
                soal_id=soal.id,
                question_text=soal.question_text,
                selected_option=jawaban.selected_option if jawaban else None,
                correct_option=soal.correct_option,
                is_correct=jawaban.is_correct if jawaban else None,
                justification=justification,
            ))
        return results

    async def _evaluate_one(self, soal: Soal, jawaban: SoalJawaban) -> dict:
        """Bangun Segment sumber dari rentang block soal ini, lalu jalankan Chain 5 di thread
        terpisah (sama seperti `regenerate_cluster` memanggil `compute_cluster`)."""
        blocks = await self.repo.get_blocks_for_chapter(soal.chapter_id)
        seg_blocks = [b for b in blocks if soal.source_reading_order_start <= b.reading_order <= soal.source_reading_order_end]
        seg = Segment(
            chapter_id=soal.chapter_id,
            title="",
            reading_order_start=soal.source_reading_order_start,
            reading_order_end=soal.source_reading_order_end,
            text="\n".join(b.readable_text for b in seg_blocks),
        )
        options = {o.label: o.opsi_text for o in soal.opsi}
        correct_langkah = [l.teks for l in sorted(soal.langkah, key=lambda l: l.urutan)]
        student_langkah = [l.teks for l in sorted(jawaban.langkah, key=lambda l: l.urutan)]
        return await asyncio.to_thread(
            quiz_evaluate.evaluate_scratchwork,
            seg, soal.question_text, options, soal.correct_option, correct_langkah, soal.kesimpulan,
            jawaban.selected_option, student_langkah,
        )
