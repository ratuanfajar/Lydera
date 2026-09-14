from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Sequence

from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalStimulus
from app.domains.quizz.schemas.quiz_request_query import QuizRequestQueryStatus
from app.domains.quizz.schemas.quiz_request_create import QuizChapterRequest
from app.domains.quizz.schemas.soal_create_request import SoalCreateRequest


class QuizRepositoryInterface(ABC):
    # Module/Chapter (validasi request)
    @abstractmethod
    async def get_module_by_id(self, module_id: int) -> Module | None: raise NotImplementedError
    @abstractmethod
    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None: raise NotImplementedError
    @abstractmethod
    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]: raise NotImplementedError

    # QuizRequest
    @abstractmethod
    async def validate_ownership_and_hierarchy(self, teacher_id: int, classroom_id: int, module_id: int, chapter_ids: list[int]) -> tuple[bool, str | None]: raise NotImplementedError
    @abstractmethod
    async def validate_classroom_ownership(self, teacher_id: int, classroom_id: int) -> bool: raise NotImplementedError
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
    async def get_chapter_links(self, quiz_request_id: int) -> Sequence[QuizChapterRequest]:
        raise NotImplementedError
    @abstractmethod
    async def link_chapter(self, quiz_request_id: int, chapter_id: int, hots_count: int, lots_count: int) -> None:
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
    
    # New Method Soal
    @abstractmethod
    async def get_quizzes_teacher(self, classroom_id: int, teacher_id:int, status: QuizRequestQueryStatus) -> Sequence[QuizRequest]: raise NotImplementedError

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
    async def save_soal(self, quiz_request_id: int, chapter_id: int, data: dict,review_priority: str, validation_notes: str | None) -> int:raise NotImplementedError
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
    async def set_review_status(self, soal: Soal, status: str) -> None: raise NotImplementedError
    @abstractmethod
    async def replace_soal_opsi(self, soal_id: int, options: dict[str, str]) -> None: raise NotImplementedError
    @abstractmethod
    async def replace_soal_langkah(self, soal_id: int, langkah: list[str]) -> None: raise NotImplementedError
    @abstractmethod
    async def save_quiz_data(self, quiz_request_id: int, classroom_id:int, status_val: str, items: List[SoalCreateRequest]) -> bool : raise NotImplementedError
    
