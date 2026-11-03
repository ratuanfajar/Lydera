from abc import ABC, abstractmethod
from typing import Sequence

from app.domains.contents.models import Block, Chapter, Fase, Cp
from app.domains.contents.schemas.blocks.regenerate_response import RegenerateResponse


class ContentRepositoryInterface(ABC):
    # Block
    @abstractmethod
    async def student_get_blocks_by_chapter_id(self, chapter_id: int, student_id: int) -> Chapter | None:
        """Retrieves all blocks belonging to a chapter."""
        raise NotImplementedError

    @abstractmethod
    async def student_get_paginated_blocks(
        self, chapter_id: int, student_id: int, limit: int, offset: int
    ) -> tuple[Chapter | None, list[Block], int]:
        """Retrieves paginated blocks for a chapter with total count."""
        raise NotImplementedError

    @abstractmethod
    async def get_teacher_blocks(self, block_ids: list[int], teacher_id: int) -> list[Block]: raise NotImplementedError

    @abstractmethod
    async def get_block_by_id(self, block_id: int) -> Block | None: raise NotImplementedError

    @abstractmethod
    async def bulk_insert_blocks(self, blocks: list[Block]) -> None: raise NotImplementedError

    @abstractmethod
    async def bulk_update_readable_text(self, update_data: list[dict]) -> bool: raise NotImplementedError

    # Fase
    @abstractmethod
    async def get_all_fases(self) -> Sequence[Fase]: raise NotImplementedError

    # CP
    @abstractmethod
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]: raise NotImplementedError

    @abstractmethod
    async def get_cp_by_id(self, cp_id: int) -> Cp | None: raise NotImplementedError

    # Chapter
    @abstractmethod
    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int: raise NotImplementedError

    @abstractmethod
    async def get_chapter_by_id(self, chapter_id: int, teacher_id: int) -> Chapter | None: raise NotImplementedError

    @abstractmethod
    async def get_current_max_order(self, chapter_id: int) -> int: raise NotImplementedError

    @abstractmethod
    async def student_create_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        """Creates chapter progress if it doesn't exist (ON CONFLICT DO NOTHING)."""
        raise NotImplementedError

    @abstractmethod
    async def student_update_chapter_progress(self, chapter_id: int, student_id: int) -> bool: raise NotImplementedError

    @abstractmethod
    async def validate_student_chapter_access(self, chapter_id: int, student_id: int) -> bool: raise NotImplementedError
