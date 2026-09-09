from abc import ABC, abstractmethod

from typing import Sequence
from app.domains.contents.models import Block, Module, Fase, Cp, Chapter, ModuleStatus

class ContentRepositoryInterface(ABC):
    @abstractmethod
    async def get_blocks_by_chapter(self, chapter_id: int) -> Sequence[Block]: pass
    @abstractmethod
    async def get_block_by_id(self, block_id: int) -> Block | None: pass
    @abstractmethod
    async def get_all_fases(self) -> Sequence[Fase]: pass
    @abstractmethod
    async def get_all_modules(self) -> Sequence[Module]: pass
    @abstractmethod
    async def get_module_by_id(self, module_id: int) -> Module | None: pass
    @abstractmethod
    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, fase_id: int | None) -> Module:pass
    @abstractmethod
    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]: pass
    @abstractmethod
    async def get_cp_by_id(self, cp_id: int) -> Cp | None: pass
    @abstractmethod
    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int: pass
    @abstractmethod
    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None: pass
    @abstractmethod
    async def get_current_max_order(self, chapter_id: int) -> int: pass
    @abstractmethod
    async def bulk_insert_blocks(self, blocks: list[Block]) -> None: pass