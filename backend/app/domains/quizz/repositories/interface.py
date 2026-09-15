from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Sequence

from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalStimulus
from app.domains.quizz.schemas.quiz_request_query import QuizRequestQueryStatus
from app.domains.quizz.schemas.quiz_request_create import QuizChapterRequest
from app.domains.quizz.schemas.soal_create_request import SoalCreateRequest
from app.domains.quizz.schemas.quiz_request_student_query import QuizRequestStudentQueryStatus
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalJawaban, SoalStimulus
from app.domains.quizz.models.quiz_progress import QuizProgress

class QuizRepositoryInterface(ABC):
    # Module/Chapter (validasi request)
    @abstractmethod
    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]: raise NotImplementedError

    # QuizRequest
    @abstractmethod
    async def validate_ownership_and_hierarchy(self, teacher_id: int, classroom_id: int, module_id: int, chapter_ids: list[int]) -> tuple[bool, str | None]: raise NotImplementedError
    @abstractmethod
    async def validate_quiz_request(self, quiz_request_id:int, teacher_id: int, classroom_id: int) -> bool: raise NotImplementedError
    @abstractmethod
    async def create_quiz_request(self, module_id: int, title:str, classroom_id:int,max_duration_minutes: int, start_time: datetime, end_time: datetime) -> QuizRequest: raise NotImplementedError
    @abstractmethod
    async def bulk_link_chapters(self, quiz_request_id: int, chapters: list[QuizChapterRequest]) -> None:
        raise NotImplementedError
    @abstractmethod
    async def update_quiz_request_status_by_id(self, quiz_request_id: int, status: str, error: str | None = None) -> None:
        raise NotImplementedError
    @abstractmethod
    async def get_quiz_request(self, quiz_request_id: int) -> QuizRequest | None: raise NotImplementedError
    @abstractmethod
    async def get_chapter_links(self, quiz_request_id: int) -> Sequence[QuizRequestChapter]: raise NotImplementedError
    @abstractmethod
    async def update_quiz_request_status(self, quiz_request: QuizRequest, status: str, error: str | None = None) -> None:
        raise NotImplementedError
    @abstractmethod
    async def update_quiz_status_publish(self, quiz_request_id: int, status: str) -> bool : raise NotImplementedError
    @abstractmethod
    async def delete_quizz(self, quiz_request_id: int) -> bool : raise NotImplementedError
    @abstractmethod
    async def check_is_quiz_done(self, student_id: int, quiz_id: int) -> bool: raise NotImplementedError
    # New Method Soal
    @abstractmethod
    async def get_quizzes_teacher(self, classroom_id: int, teacher_id:int, status: QuizRequestQueryStatus) -> Sequence[QuizRequest]: raise NotImplementedError
    @abstractmethod
    async def get_quizzes_student(self, classroom_id: int, student_id:int, status: QuizRequestStudentQueryStatus) -> Sequence[QuizRequest]: raise NotImplementedError

    @abstractmethod
    async def get_quiz_progress(self, quiz_request_id: int, student_id: int) -> QuizProgress | None: raise NotImplementedError

    @abstractmethod
    async def update_soal_jawaban(
        self,
        jawaban_id:int,
        selected_option: str,
        is_correct: bool,
        langkah: list[str]
    ) -> None: raise NotImplementedError

    @abstractmethod
    async def update_quiz_request_settings(
        self,
        quiz_request_id: int,
        title: Optional[str] = None,
        max_duration_minutes: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[QuizRequest]:
        """Updates quiz request scheduling and title settings."""
        raise NotImplementedError

    @abstractmethod
    async def get_quiz_teacher(self, classroom_id: int, teacher_id:int, id:int) -> QuizRequest | None: raise NotImplementedError

    # Soal
    @abstractmethod
    async def get_soal_by_id(self, soal_id: int) -> Soal | None: raise NotImplementedError
    @abstractmethod
    async def get_soal_for_request(self, quiz_request_id: int) -> Sequence[Soal]: raise NotImplementedError
    @abstractmethod
    async def get_stimulus_by_id(self, stimulus_id: int) -> SoalStimulus | None: raise NotImplementedError
    @abstractmethod
    async def get_soal_by_stimulus(self, stimulus_id: int) -> Sequence[Soal]: raise NotImplementedError
    @abstractmethod
    async def update_stimulus_text(self, stimulus: SoalStimulus, readable_text: str) -> None: raise NotImplementedError
    @abstractmethod
    async def replace_soal_opsi(self, soal_id: int, options: dict[str, str]) -> None: raise NotImplementedError
    @abstractmethod
    async def replace_soal_langkah(self, soal_id: int, langkah: list[str]) -> None: raise NotImplementedError
    @abstractmethod
    async def save_quiz_data(self, quiz_request_id: int, classroom_id:int, status_val: str, items: List[SoalCreateRequest]) -> bool : raise NotImplementedError
    

    # SoalJawaban (jawaban siswa)
    @abstractmethod
    async def get_soal_jawaban(self, soal_id: int, student_id: int) -> SoalJawaban | None: raise NotImplementedError
    @abstractmethod
    async def create_soal_jawaban(self, soal_id: int, student_id: int, selected_option: str,
        is_correct: bool, langkah: list[str]) -> int:
        raise NotImplementedError
    @abstractmethod
    async def get_jawaban_for_request(self, quiz_request_id: int, student_id: int) -> Sequence[SoalJawaban]:
        raise NotImplementedError
    @abstractmethod
    async def save_evaluation(self, jawaban: SoalJawaban, divergence_step: int | None,
    diagnosis: str, personalized_justification: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_or_create_quiz_progress(self, student_id: int, quiz_id: int) -> tuple[QuizRequest, QuizProgress]:
        """Fetches quiz request along with the student's progress record, creating one if non-existent."""
    pass
    @abstractmethod
    async def get_quiz_questions_with_answers(self, quiz_id: int, student_id: int) -> list[Soal]: raise NotImplementedError
    @abstractmethod
    async def mark_quiz_completed(self, student_id: int, quiz_id: int) -> None:
        """Marks student progress as done upon timer expiration."""
    pass
