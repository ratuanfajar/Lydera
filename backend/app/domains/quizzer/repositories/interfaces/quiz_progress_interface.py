from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.quizzer.models import QuizRequest, Soal, SoalJawaban
from app.domains.quizzer.models.quiz_progress import QuizProgress


class QuizProgressRepositoryInterface(ABC):
    @abstractmethod
    async def get_quiz_progress(self, quiz_request_id: int, student_id: int) -> QuizProgress | None: raise NotImplementedError

    @abstractmethod
    async def get_or_create_quiz_progress(self, student_id: int, quiz_id: int) -> tuple[QuizRequest, QuizProgress]:
        """Fetches quiz request along with the student's progress record, creating one if non-existent."""
        raise NotImplementedError

    @abstractmethod
    async def check_is_quiz_done(self, student_id: int, quiz_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def mark_quiz_completed(self, student_id: int, quiz_id: int) -> None:
        """Marks student progress as done upon timer expiration."""
        raise NotImplementedError

    @abstractmethod
    async def get_soal_jawaban(self, soal_id: int, student_id: int) -> SoalJawaban | None: raise NotImplementedError

    @abstractmethod
    async def create_soal_jawaban(self, soal_id: int, student_id: int, selected_option: str, is_correct: bool) -> int: raise NotImplementedError

    @abstractmethod
    async def update_soal_jawaban(self, jawaban_id: int, selected_option: str, is_correct: bool) -> None: raise NotImplementedError

    @abstractmethod
    async def get_jawaban_for_request(self, quiz_request_id: int, student_id: int) -> Sequence[SoalJawaban]: raise NotImplementedError

    @abstractmethod
    async def save_evaluation(self, jawaban: SoalJawaban, evaluation: dict) -> None: raise NotImplementedError

    @abstractmethod
    async def add_step(self, soal_id: int, student_id: int, text: str) -> dict: raise NotImplementedError

    @abstractmethod
    async def remove_step(self, step_id: int, student_id: int) -> bool: raise NotImplementedError

