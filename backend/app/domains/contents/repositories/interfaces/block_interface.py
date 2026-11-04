from abc import ABC, abstractmethod

from app.domains.contents.models import Block


class BlockRepositoryInterface(ABC):
    @abstractmethod
    async def get_teacher_blocks(self, block_ids: list[int], teacher_id: int) -> list[Block]: raise NotImplementedError

    @abstractmethod
    async def bulk_update_readable_text(self, update_data: list[dict]) -> bool: raise NotImplementedError

    @abstractmethod
    async def get_block_by_id(self, block_id: int) -> Block | None: raise NotImplementedError
