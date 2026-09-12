from abc import ABC, abstractmethod

from typing import Sequence
from app.domains.contents.models import Block, Module, Fase, Cp, Chapter, ModuleStatus
from app.domains.contents.schemas.module.student_module_request import StudentModuleStatus
from app.domains.contents.schemas.module.teacher_module_request import TeacherModuleStatus

class ContentRepositoryInterface(ABC):
    # Block
    @abstractmethod
    async def student_get_blocks_by_chapter_id(self, chapter_id: int, student_id:int) -> Chapter | None:
        """Retrieves all blocks belonging to a chapter."""
        raise NotImplementedError
    @abstractmethod
    async def get_block_by_id(self, block_id: int) -> Block | None: raise NotImplementedError
    @abstractmethod
    async def bulk_insert_blocks(self, blocks: list[Block]) -> None: raise NotImplementedError

    # Fase
    @abstractmethod
    async def get_all_fases(self) -> Sequence[Fase]: raise NotImplementedError

    # Module
    @abstractmethod
    async def get_module_by_id(self, module_id: int) -> Module | None: raise NotImplementedError
    @abstractmethod
    async def create_module_teacher(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id:int, fase_id: int | None) -> Module | None :raise NotImplementedError
    @abstractmethod
    async def get_all_modules_student(self, classroom_id: int, student_id: int, status:StudentModuleStatus ) -> Sequence[Module]: raise NotImplementedError
    @abstractmethod
    async def get_detail_module_student(self, module_id:int, classroom_id: int, student_id: int) -> Module | None: raise NotImplementedError
    @abstractmethod
    async def get_all_modules_teachers(self, classroom_id:int, teacher_id:int, status: TeacherModuleStatus, search: str | None) -> Sequence[Module]: raise NotImplementedError
    @abstractmethod
    async def get_detail_module_teacher(self, module_id:int, classroom_id: int, teacher_id: int) -> Module | None: raise NotImplementedError
    @abstractmethod
    async def publish_module(self, module_id:int, teacher_id:int) -> True: raise NotImplementedError
    @abstractmethod
    async def verify_chapter_teacher(self, chapter_id: int, teacher_id: int) -> bool: raise NotImplementedError

    # CP
    @abstractmethod
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]: raise NotImplementedError
    @abstractmethod
    async def get_cp_by_id(self, cp_id: int) -> Cp | None: raise NotImplementedError

    # Chapter
    @abstractmethod
    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int: raise NotImplementedError

    @abstractmethod
    async def student_upsert_chapter_progress(self, student_id: int, chapter_id: int) -> bool:
        """Creates chapter progress if it doesn't exist (ON CONFLICT DO NOTHING)."""
        raise NotImplementedError

    @abstractmethod
    async def student_update_chapter_progress(self, chapter_id: int, student_id:int) -> bool: raise NotImplementedError

    @abstractmethod
    async def get_chapter_by_id(self, chapter_id: int, teacher_id: int) -> Chapter | None: raise NotImplementedError

    @abstractmethod
    async def get_current_max_order(self, chapter_id: int) -> int: raise NotImplementedError
    