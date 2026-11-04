from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import delete, select, text
from sqlalchemy.orm import selectinload

from app.core.db import AsyncSession
from app.core.exceptions import NotFoundException
from app.domains.quizz.models import (
    QuizRequest, Soal, SoalJawaban, SoalJawabanLangkah,
)
from app.domains.quizz.models.quiz_progress import QuizProgress
from app.domains.quizz.repositories.interfaces.quiz_progress_interface import (
    QuizProgressRepositoryInterface,
)


class QuizProgressRepository(QuizProgressRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_is_quiz_done(self, student_id: int, quiz_id: int) -> bool:
        stmt = select(QuizProgress.is_done).where(
            QuizProgress.quiz_request_id == quiz_id,
            QuizProgress.student_id == student_id,
        )
        return bool(await self.db.scalar(stmt))

    async def add_step(self, soal_id: int, student_id: int, step: str) -> dict:
        raw_sql = text("""
            WITH target_jawaban AS (
                INSERT INTO soal_jawaban (soal_id, student_id)
                VALUES (:soal_id, :student_id)
                ON CONFLICT (soal_id, student_id)
                DO UPDATE SET soal_id = EXCLUDED.soal_id 
                RETURNING id
            ),
            next_seq AS (
                SELECT COALESCE(MAX(urutan), 0) + 1 AS next_urutan
                FROM soal_jawaban_langkah
                WHERE jawaban_id = (SELECT id FROM target_jawaban)
            )
            INSERT INTO soal_jawaban_langkah (jawaban_id, urutan, teks)
            SELECT 
                (SELECT id FROM target_jawaban), 
                (SELECT next_urutan FROM next_seq), 
                :teks
            RETURNING id, urutan, teks;
        """)
        result = await self.db.execute(
            raw_sql,
            {"soal_id": soal_id, "student_id": student_id, "teks": step}
        )
        await self.db.flush()
        row = result.mappings().one()
        return dict(row)

    async def remove_step(self, step_id: int, student_id: int) -> bool:
        stmt = (
            delete(SoalJawabanLangkah)
            .where(
                SoalJawabanLangkah.id == step_id,
                SoalJawabanLangkah.jawaban_id.in_(
                    select(SoalJawaban.id).where(SoalJawaban.student_id == student_id)
                ),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def get_or_create_quiz_progress(self, student_id: int, quiz_id: int) -> tuple[QuizRequest, QuizProgress]:
        quiz = await self.db.get(QuizRequest, quiz_id)
        if not quiz:
            raise NotFoundException("Kuis tidak ditemukan.")
        stmt = select(QuizProgress).where(
            QuizProgress.quiz_request_id == quiz_id,
            QuizProgress.student_id == student_id
        ).order_by(QuizProgress.id.desc()).limit(1)

        progress = (await self.db.scalars(stmt)).first()

        if not progress:
            progress = QuizProgress(
                quiz_request_id=quiz_id,
                student_id=student_id,
                attempt_count=0,
                is_done=False,
            )
            self.db.add(progress)
            await self.db.flush()

        return quiz, progress

    async def mark_quiz_completed(self, student_id: int, quiz_id: int) -> None:
        stmt = select(QuizProgress).where(
            QuizProgress.quiz_request_id == quiz_id,
            QuizProgress.student_id == student_id,
        )

        progress = (await self.db.scalars(stmt)).one_or_none()

        if progress and not progress.is_done:
            progress.is_done = True
            progress.completed_at = datetime.now(timezone.utc)
            await self.db.commit()

    async def update_soal_jawaban(self, jawaban_id: int, selected_option: str, is_correct: bool,
                                #    langkah: list[str]
                                   ) -> None:
        jawaban = await self.db.get(SoalJawaban, jawaban_id)
        if not jawaban:
            return

        jawaban.selected_option = selected_option
        jawaban.is_correct = is_correct

        # await self.db.execute(
        #     delete(SoalJawabanLangkah).where(SoalJawabanLangkah.jawaban_id == jawaban_id)
        # )

        # if langkah:
        #     new_steps = [
        #         {"jawaban_id": jawaban_id, "urutan": index, "teks": step_text}
        #         for index, step_text in enumerate(langkah, start=1)
        #     ]
        #     await self.db.execute(insert(SoalJawabanLangkah), new_steps)

    async def get_soal_jawaban(self, soal_id: int, student_id: int) -> SoalJawaban | None:
        stmt = (
            select(SoalJawaban)
            .where(SoalJawaban.soal_id == soal_id, SoalJawaban.student_id == student_id)
            .options(selectinload(SoalJawaban.langkah))
        )
        result = await self.db.scalars(stmt)
        return result.first()

    async def create_soal_jawaban(self, soal_id: int, student_id: int, selected_option: str,
    is_correct: bool,
    # langkah: list[str]
    ) -> int:
        jawaban = SoalJawaban(
            soal_id=soal_id,
            student_id=student_id,
            selected_option=selected_option,
            is_correct=is_correct,
        )
        self.db.add(jawaban)
        await self.db.flush()

        # for urutan, teks in enumerate(langkah, start=1):
        #     self.db.add(SoalJawabanLangkah(jawaban_id=jawaban.id, urutan=urutan, teks=teks))
        await self.db.flush()

        return jawaban.id

    async def get_jawaban_for_request(self, quiz_request_id: int, student_id: int) -> Sequence[SoalJawaban]:
        stmt = (
            select(SoalJawaban)
            .join(Soal, SoalJawaban.soal_id == Soal.id)
            .where(Soal.quiz_request_id == quiz_request_id, SoalJawaban.student_id == student_id)
            .options(selectinload(SoalJawaban.langkah))
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_quiz_progress(self, quiz_request_id: int, student_id: int) -> Optional[QuizProgress]:
        """Fetches the progress record for a specific student and quiz request."""
        stmt = (
            select(QuizProgress)
            .where(
                QuizProgress.quiz_request_id == quiz_request_id,
                QuizProgress.student_id == student_id,
            )
            .order_by(QuizProgress.attempt_count.desc())
            .limit(1)
        )
        result = await self.db.scalars(stmt)
        return result.first()

    async def save_evaluation(self, jawaban: SoalJawaban, divergence_step: int | None,
                               diagnosis: str, personalized_justification: str) -> None:
        jawaban.divergence_step = divergence_step
        jawaban.diagnosis = diagnosis
        jawaban.personalized_justification = personalized_justification
        jawaban.evaluated_at = datetime.now(timezone.utc)
