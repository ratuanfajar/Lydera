from sqlalchemy import select, update

from app.core.db import AsyncSession
from app.core.exceptions import ForbiddenException
from app.domains.classrooms.models.classroom import Classroom
from app.domains.contents.models import Block, Chapter, Module
from app.domains.contents.repositories.interfaces.block_interface import (
    BlockRepositoryInterface,
)


class BlockRepository(BlockRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_block(self, block: Block):
        await self.db.delete(block)
        await self.db.commit()

    async def get_teacher_blocks(self, block_ids: list[int], teacher_id: int) -> list[Block]:
        unique_ids = list(set(block_ids))
        stmt = (
            select(Block)
            .join(Chapter, Block.chapter_id == Chapter.id)
            .join(Module, Chapter.module_id == Module.id)
            .join(Classroom, Module.classroom_id == Classroom.id)
            .where(
                Block.id.in_(unique_ids),
                Classroom.teacher_id == teacher_id
            )
        )
        blocks = (await self.db.scalars(stmt)).all()

        if len(blocks) != len(unique_ids):
            raise ForbiddenException("Tidak punya akses, beberapa block bukan punya mu.")
        return blocks

    async def bulk_update_readable_text(self, update_data: list[dict]) -> bool:
        await self.db.execute(update(Block), update_data)
        await self.db.commit()
        return True

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.db.get(Block, block_id)

    
    async def get_neighbor_blocks(self, chapter_id: int, reading_order: int) -> list[Block]:
        before = (
            select(Block).where(Block.chapter_id == chapter_id, Block.reading_order < reading_order)
            .order_by(Block.reading_order.desc()).limit(1)
        )
        after = (
            select(Block).where(Block.chapter_id == chapter_id, Block.reading_order > reading_order)
            .order_by(Block.reading_order.asc()).limit(1)
        )
        return [*(await self.db.scalars(before)).all(), *(await self.db.scalars(after)).all()]
