from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Sequence

from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizzer.models import QuizRequest, QuizRequestChapter, Soal, SoalStimulus
from app.domains.quizzer.schemas.quiz_request_query import QuizRequestQueryStatus
from app.domains.quizzer.schemas.quiz_request_create import QuizChapterRequest
from app.domains.quizzer.schemas.soal_create_request import SoalCreateRequest
from app.domains.quizzer.schemas.quiz_request_student_query import QuizRequestStudentQueryStatus
from app.domains.quizzer.models.quiz_progress import QuizProgress


class QuizRequestRepositoryInterface(ABC):
    @abstractmethod
    async def validate_ownership_and_hierarchy(self, teacher_id: int, classroom_id: int, module_id: int, chapter_ids: list[int]) -> tuple[bool, str | None]: raise NotImplementedError

    @abstractmethod
    async def refresh_quiz_progress(self, progress: QuizProgress) -> None: raise NotImplementedError

    @abstractmethod
    async def validate_quiz_request(self, quiz_request_id: int, teacher_id: int, classroom_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def has_quiz_progress(self, quiz_request_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def create_quiz_request(self, module_id: int, title: str, classroom_id: int, max_duration_minutes: int, max_retry: int, start_time: datetime, end_time: datetime) -> QuizRequest: raise NotImplementedError

    @abstractmethod
    async def bulk_link_chapters(self, quiz_request_id: int, chapters: list[QuizChapterRequest]) -> None: raise NotImplementedError

    @abstractmethod
    async def update_quiz_request_status_by_id(self, quiz_request_id: int, status: str, error: str | None = None) -> None: raise NotImplementedError

    @abstractmethod
    async def get_quiz_request(self, quiz_request_id: int) -> QuizRequest | None: raise NotImplementedError

    @abstractmethod
    async def get_chapter_links(self, quiz_request_id: int) -> Sequence[QuizRequestChapter]: raise NotImplementedError

    @abstractmethod
    async def update_quiz_request_status(self, quiz_request: QuizRequest, status: str, error: str | None = None) -> None: raise NotImplementedError

    @abstractmethod
    async def update_quiz_status_publish(self, quiz_request_id: int, status: str) -> bool: raise NotImplementedError

    @abstractmethod
    async def update_quiz_request_settings(
        self,
        quiz_request_id: int,
        title: Optional[str] = None,
        max_duration_minutes: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[QuizRequest]: raise NotImplementedError

    @abstractmethod
    async def delete_quizz(self, quiz_request_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def get_quizzes_teacher(self, classroom_id: int, teacher_id: int, status: QuizRequestQueryStatus) -> Sequence[QuizRequest]: raise NotImplementedError

    @abstractmethod
    async def get_quizzes_student(self, classroom_id: int, student_id: int, status: QuizRequestStudentQueryStatus) -> Sequence[QuizRequest]: raise NotImplementedError

    @abstractmethod
    async def get_quiz_teacher(self, classroom_id: int, teacher_id: int, id: int) -> QuizRequest | None: raise NotImplementedError

    @abstractmethod
    async def get_students(self, classroom_id: int, teacher_id: int, quiz_request_id: int) -> Sequence[QuizProgress]: raise NotImplementedError

    @abstractmethod
    async def is_student_in_classroom(self, student_id: int, classroom_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def save_quiz_data(self, quiz_request_id: int, classroom_id: int, status_val: str, items: List[SoalCreateRequest], coverage_report: Optional[dict] = None) -> bool: raise NotImplementedError
