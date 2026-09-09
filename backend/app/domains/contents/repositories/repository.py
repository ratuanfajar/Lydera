from sqlalchemy import func, select
from typing import Sequence
from app.domains.contents.models import Block, Module, Chapter, Fase, Cp, ModuleStatus
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.core.db import AsyncSession

class ContentRepository(ContentRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_blocks_by_chapter(self, chapter_id: int) -> Sequence[Block]:
        stmt = select(Block).where(Block.chapter_id == chapter_id).order_by(Block.reading_order)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.db.get(Block, block_id)

    async def get_all_fases(self) -> Sequence[Fase]:
        stmt = select(Fase).order_by(Fase.kode)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_all_modules(self) -> Sequence[Module]:
        stmt = select(Module).order_by(Module.id)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.db.get(Module, module_id)

    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, fase_id: int | None) -> Module:
        new_module = Module(title=title, description=description, status=status.name, classroom_id=classroom_id, fase_id=fase_id)
        self.db.add(new_module)
        await self.db.flush()
        return new_module

    async def get_cps_by_fase_id(self, fase_id: int) -> Sequence[Cp]:
        stmt = select(Cp).where(Cp.fase_id == fase_id).order_by(Cp.domain)
        result = await self.db.scalars(stmt)
        return result.all()

    async def get_cp_by_id(self, cp_id: int) -> Cp | None:
        return await self.db.get(Cp, cp_id)

    async def create_chapter(self, module_id: int, source_file: str, number: int | None = None, title: str | None = None, cp_id: int | None = None) -> int:
        new_chapter = Chapter(
            module_id=module_id, 
            source_file=source_file, 
            number=number, 
            title=title, 
            cp_id=cp_id
        )
        self.db.add(new_chapter)
        await self.db.flush()
        return new_chapter.id

    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None:
        return await self.db.get(Chapter, chapter_id)

    async def get_current_max_order(self, chapter_id: int) -> int:
        stmt = select(func.max(Block.reading_order)).where(Block.chapter_id == chapter_id)
        result = await self.db.scalar(stmt)
        return result or 0

    async def bulk_insert_blocks(self, blocks: list[Block]) -> None:
        self.db.add_all(blocks)
        await self.db.flush()
