from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.contents.models import Block
from app.domains.quizz.models import Soal, SoalStimulus


class SoalRepositoryInterface(ABC):
    @abstractmethod
    async def get_blocks_for_chapter(self, chapter_id: int) -> Sequence[Block]: raise NotImplementedError

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
    async def get_quiz_questions_with_answers(self, quiz_id: int, student_id: int) -> list[Soal]: raise NotImplementedError
