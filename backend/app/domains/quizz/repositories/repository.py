from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import Label, and_, delete, func, insert, or_, select
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.core.db import AsyncSession
from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalLangkah, SoalOpsi, SoalStimulus
from app.domains.quizz.repositories.interface import QuizRepositoryInterface
from app.domains.quizz.schemas.quiz_request_query import QuizRequestQueryStatus
from app.domains.classrooms.models.classroom import Classroom
from app.domains.quizz.schemas.soal_create_request import SoalCreateRequest
from app.domains.quizz.models.quiz_progress import QuizProgress
from app.domains.quizz.models.quiz_request import QuizRequestStatus
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQueryStatus


class QuizRepository(QuizRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_quiz_request(self, quiz_request_id:int, teacher_id: int, classroom_id: int) -> bool:
        stmt = (
            select(QuizRequest.id)
            .join(QuizRequest.module)
            .join(Module.classroom)
            .where(
                QuizRequest.id == quiz_request_id,
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def validate_classroom_ownership(self, teacher_id: int, classroom_id: int) -> bool:
        stmt = select(Classroom.id).where(
            Classroom.id == classroom_id,
            Classroom.teacher_id == teacher_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
    
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
    async def validate_ownership_and_hierarchy(
        self, teacher_id: int, classroom_id: int, module_id: int, chapter_ids: list[int]
    ) -> tuple[bool, Optional[str]]:
        stmt_module = (
            select(Module)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Module.id == module_id,
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,
            )
        )
        module_res = await self.db.execute(stmt_module)
        if not module_res.scalar_one_or_none():
            return False, "Modul atau kelas tidak ditemukan / tidak valid untuk guru ini."

        stmt_chapters = (
            select(Chapter.id)
            .join(Block, Block.chapter_id == Chapter.id)
            .where(
                Chapter.id.in_(chapter_ids),
                Chapter.module_id == module_id,
            )
            .distinct()
        )
        valid_chapters = (await self.db.execute(stmt_chapters)).scalars().all()

        if len(valid_chapters) != len(set(chapter_ids)):
            return False, "Beberapa chapter_id tidak valid atau tidak termasuk dalam modul ini."

        return True, None

    async def update_quiz_request_settings(
        self,
        quiz_request_id: int,
        title: Optional[str] = None,
        max_duration_minutes: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[QuizRequest]:
        quiz = await self.db.get(QuizRequest, quiz_request_id)
        if not quiz:
            return None

        if title is not None:
            quiz.title = title
        if max_duration_minutes is not None:
            quiz.max_duration_minutes = max_duration_minutes
        if start_time is not None:
            quiz.start_time = start_time
        if end_time is not None:
            quiz.end_time = end_time

        await self.db.flush()
        return quiz
    
    async def create_quiz_request(self, module_id: int, title:str, classroom_id:int,max_duration_minutes: int, start_time: datetime, end_time: datetime) -> QuizRequest:
        new_request = QuizRequest(
            module_id=module_id,
            classroom_id=classroom_id,
            title=title,
            status="queued",
            max_duration_minutes=max_duration_minutes,
            start_time=start_time,
            end_time=end_time,
        )
        self.db.add(new_request)
        await self.db.flush()
        return new_request.id

    async def bulk_link_chapters(self, quiz_request_id: int, chapters: list[QuizRequestChapter]) -> None:
        values = [
            {
                "quiz_request_id": quiz_request_id,
                "chapter_id": item.chapter_id,
                "hots_count": item.hots_count,
                "lots_count": item.lots_count,
            }
            for item in chapters
        ]
        await self.db.execute(insert(QuizRequestChapter), values)

    async def update_quiz_request_status_by_id(self, quiz_request_id: int, status: str, error: Optional[str] = None) -> None:
        quiz = await self.db.get(QuizRequest, quiz_request_id)
        if quiz:
            quiz.status = status
            if error:
                quiz.error = error
            await self.db.flush()

    async def get_chapter_links(self, quiz_request_id: int) -> Sequence[QuizRequestChapter]:
        stmt = select(QuizRequestChapter).where(
            QuizRequestChapter.quiz_request_id == quiz_request_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

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

    async def delete_quizz(self, quiz_request_id: int) -> bool : 
        stmt = delete(QuizRequest).where(QuizRequest.id == quiz_request_id)
        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.rowcount > 0

        
    def _get_soal_count(self) -> Label[int]:
        """Synchronous subquery builder returning question count per quiz_request."""
        return (
            select(func.count(Soal.id))
            .where(Soal.quiz_request_id == QuizRequest.id)
            .scalar_subquery()
            .label("question_counts")
        )

    # Teacher
    async def get_quizzes_teacher(self, classroom_id: int, teacher_id:int, status: QuizRequestQueryStatus) -> Sequence[QuizRequest]:
        soal_count_subquery = self._get_soal_count()

        stmt = (
            select(QuizRequest, soal_count_subquery)
            .join(QuizRequest.module)
            .join(Module.classroom)
            .where(
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id,  # Validates classroom ownership
            )
            .options(
                joinedload(QuizRequest.module).joinedload(Module.classroom)
            )
            .order_by(QuizRequest.id.desc())
        )

        if status != QuizRequestQueryStatus.ALL:
            stmt = stmt.where(QuizRequest.status_published == status.value)

        result = await self.db.execute(stmt)
        rows = result.unique().all()

        quizzes = []
        for quiz, count in rows:
            quiz.question_counts = count or 0
            quizzes.append(quiz)

        return quizzes

    async def get_quizzes_student(self, classroom_id: int, student_id:int, status: QuizRequestStudentQueryStatus) -> Sequence[QuizRequest]: 

        soal_count_subquery = self._get_soal_count()
        
        progress_join = and_(
            QuizProgress.quiz_request_id == QuizRequest.id,
            QuizProgress.student_id == student_id
        )

        stmt = (
            select(QuizRequest, soal_count_subquery)
            .outerjoin(QuizProgress, progress_join)
            .where(
                QuizRequest.classroom_id == classroom_id,
                QuizRequest.status_published == QuizRequestStatus.PUBLISH
            )
            .options(
                joinedload(QuizRequest.module),
                contains_eager(QuizRequest.quiz_progress)
            )
            .order_by(QuizRequest.start_time.desc())
        )

        if status == QuizRequestStudentQueryStatus.DONE:
            stmt = stmt.where(QuizProgress.is_done.is_(True))

        elif status == QuizRequestStudentQueryStatus.NOT_DONE:
            stmt = stmt.where(
                or_(
                    QuizProgress.id.is_(None),
                    QuizProgress.is_done.is_(False),
                )
            )

        result = await self.db.execute(stmt)
        rows = result.unique().all()

        quizzes = []
        for quiz, count in rows:
            setattr(quiz, "question_counts", count or 0)
            quizzes.append(quiz)
        return quizzes

    async def get_quiz_teacher(self, classroom_id: int, teacher_id:int, id:int) -> QuizRequest | None: 
        stmt = (
            select(QuizRequest)
            .join(QuizRequest.module)
            .join(Module.classroom)
            .where(
                QuizRequest.id == id,
                Module.classroom_id == classroom_id,
                Classroom.teacher_id == teacher_id
            )
            .options(
                contains_eager(QuizRequest.module),
                selectinload(QuizRequest.chapter_links),
                selectinload(QuizRequest.soals).options(
                    selectinload(Soal.stimulus),
                    selectinload(Soal.opsi),
                    selectinload(Soal.langkah),
                ),
            ).order_by(QuizRequest.id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_quiz_status_publish(self, quiz_request_id: int, status: str, error: Optional[str] = None) -> bool:
        quiz_req = await self.db.get(QuizRequest, quiz_request_id)
        if not quiz_req:
            return False

        quiz_req.status_published = status
        if error is not None:
            quiz_req.error = error

        await self.db.flush()
        return True

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

    async def save_quiz_data(self, quiz_request_id: int, classroom_id:int, status_val: str, items: List[SoalCreateRequest]) -> bool:
        quiz_req = await self.db.get(QuizRequest, quiz_request_id)

        if not quiz_req:
            return False

        quiz_req.status = status_val
        quiz_req.classroom_id = classroom_id

        await self.db.execute(delete(Soal).where(Soal.quiz_request_id == quiz_request_id))
        await self.db.execute(delete(SoalStimulus).where(SoalStimulus.quiz_request_id == quiz_request_id))

        stimulus_objects = []
        stimulus_map = {}

        for idx, item in enumerate(items):
            if item.data.stimulus:
                stim = SoalStimulus(
                    quiz_request_id=quiz_request_id,
                    chapter_id=item.chapter_id,
                    source_markup=item.data.stimulus.source_markup or "",
                    readable_text=item.data.stimulus.readable_text,
                    source_reading_order_start=(
                        item.data.stimulus.source_reading_order_start
                        if item.data.stimulus.source_reading_order_start is not None
                        else item.data.reading_order_start
                    ),
                    source_reading_order_end=(
                        item.data.stimulus.source_reading_order_end
                        if item.data.stimulus.source_reading_order_end is not None
                        else item.data.reading_order_end
                    ),
                )
                stimulus_objects.append(stim)
                stimulus_map[idx] = stim

        if stimulus_objects:
            self.db.add_all(stimulus_objects)
            await self.db.flush()

        soal_objects = []
        for idx, item in enumerate(items):
            stim_id = stimulus_map[idx].id if idx in stimulus_map else None
            soal = Soal(
                quiz_request_id=quiz_request_id,
                chapter_id=item.chapter_id,
                stimulus_id=stim_id,
                bloom_level=item.data.bloom_level,
                question_text=item.data.question_text,
                correct_option=item.data.correct_option,
                kesimpulan=item.data.kesimpulan,
                source_reading_order_start=item.data.reading_order_start,
                source_reading_order_end=item.data.reading_order_end,
                review_priority=item.review_priority,
                validation_notes=item.validation_notes,
            )
            soal_objects.append(soal)
        self.db.add_all(soal_objects)
        await self.db.flush()

        opsi_objects = []
        langkah_objects = []

        for idx, item in enumerate(items):
            parent_soal_id = soal_objects[idx].id

            for label, text in item.data.options.items():
                opsi_objects.append(
                    SoalOpsi(soal_id=parent_soal_id, label=label, opsi_text=text)
                )

            for step_idx, step_text in enumerate(item.data.langkah, start=1):
                langkah_objects.append(
                    SoalLangkah(soal_id=parent_soal_id, urutan=step_idx, teks=step_text)
                )

        self.db.add_all(opsi_objects)
        self.db.add_all(langkah_objects)

        await self.db.commit()
        return True
        
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
