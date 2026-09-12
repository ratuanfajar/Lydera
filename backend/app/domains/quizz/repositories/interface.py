from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizz.models import QuizRequest, QuizRequestChapter, Soal, SoalStimulus


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
    async def create_quiz_request(self, module_id: int) -> int: raise NotImplementedError
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

    # Soal
    @abstractmethod
    async def save_soal(self, quiz_request_id: int, chapter_id: int, data: dict,
                         review_priority: str, validation_notes: str | None) -> int:
        raise NotImplementedError
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
