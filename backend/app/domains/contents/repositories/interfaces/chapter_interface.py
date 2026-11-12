from abc import ABC, abstractmethod
from typing import Tuple

from app.domains.contents.models import Block, Chapter, Cp
from app.domains.jobs.models import Job


class ChapterRepositoryInterface(ABC):
    @abstractmethod
    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int: raise NotImplementedError

    @abstractmethod
    async def get_chapter_by_id(self, chapter_id: int, teacher_id: int) -> Chapter | None : raise NotImplementedError # type: ignore

    @abstractmethod
    async def get_current_max_order(self, chapter_id: int) -> int: raise NotImplementedError

    @abstractmethod
    async def bulk_insert_blocks(self, blocks: list[Block]) -> None: raise NotImplementedError

    @abstractmethod
    async def verify_chapter_teacher(self, chapter_id: int, teacher_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def student_get_blocks_by_chapter_id(self, chapter_id: int, student_id: int) -> Chapter | None:
        """Retrieves all blocks belonging to a chapter."""
        raise NotImplementedError

    @abstractmethod
    async def get_current_max_order(self, chapter_id: int) -> int: raise NotImplementedError

    @abstractmethod
    async def student_get_paginated_blocks(
        self, chapter_id: int, student_id: int, limit: int, offset: int
    ) -> tuple[Chapter | None, list[Block], int]:
        """Retrieves paginated blocks for a chapter with total count."""
        raise NotImplementedError

    @abstractmethod
    async def student_create_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        """Creates chapter progress if it doesn't exist (ON CONFLICT DO NOTHING)."""
        raise NotImplementedError

    @abstractmethod
    async def student_update_chapter_progress(self, chapter_id: int, student_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def validate_student_chapter_access(self, chapter_id: int, student_id: int) -> bool: raise NotImplementedError

