import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Sequence
from app.domains.contents.models import Block, Fase, Module, Chapter, Cp, ModuleStatus
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.core.exceptions import BadRequestException, NotFoundException

class ContentService:
    def __init__(self, repo: ContentRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db
        self.READING_ORDER_STEP = 10

    async def get_blocks_by_chapter(self, chapter_id: int) -> Sequence[Block]:
        return await self.repo.get_blocks_by_chapter(chapter_id)

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.repo.get_block_by_id(block_id)

    async def get_all_fases(self) -> Sequence[Fase]:
        return await self.repo.get_all_fases()

    async def get_all_modules(self) -> Sequence[Module]:
        return await self.repo.get_all_modules()

    async def get_module_by_id(self, module_id: int) -> Module | None:
        return await self.repo.get_module_by_id(module_id)

    async def get_chapter_by_id(self, chapter_id: int) -> Chapter | None:
        return await self.repo.get_chapter_by_id(chapter_id)

    async def get_cps_by_module_id(self, module_id: int) -> Sequence[Cp]:
        module = await self.repo.get_module_by_id(module_id)
        if not module:
            raise NotFoundException("modul tidak ditemukan")
        if module.fase_id is None:
            return []
        return await self.repo.get_cps_by_fase_id(module.fase_id)


    # --- WRITE OPERATIONS (Butuh commit/rollback) ---
    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, fase_id: int | None) -> Module:
        try:
            module = await self.repo.create_module(title, description, status, classroom_id, fase_id)
            await self.db.commit()
            await self.db.refresh(module)
            return module
        except Exception as e:
            await self.db.rollback()
            raise e

    async def update_block_text(self, block_id: int, new_text: str) -> None:
        try:
            block = await self.repo.get_block_by_id(block_id)
            if block:
                block.readable_text = new_text
                await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise e

    async def validate_and_create_chapter(self, module_id: int, cp_id: int | None, number: int | None, title: str | None, source_file: str) -> int:
        """Menggantikan validasi panjang di router."""
        try:
            module = await self.repo.get_module_by_id(module_id)
            if not module:
                raise NotFoundException("modul tidak ditemukan")

            if cp_id is not None:
                cp = await self.repo.get_cp_by_id(cp_id)
                if not cp:
                    raise NotFoundException(f"cp_id={cp_id} tidak ditemukan")
                if cp.fase_id != module.fase_id:
                    raise BadRequestException("cp_id tidak sesuai fase modul ini")

            chapter_id = await self.repo.create_chapter(
                module_id=module_id, 
                source_file=source_file, 
                number=number, 
                title=title, 
                cp_id=cp_id
            )
            await self.db.commit()
            return chapter_id
        except Exception as e:
            await self.db.rollback()
            raise e

    async def ingest_annotated_json(self, annotated_path: str, chapter_id: int) -> int:
        try:
            blocks_data = json.loads(Path(annotated_path).read_text(encoding="utf-8"))
            base_order = await self.repo.get_current_max_order(chapter_id)
            
            blocks_to_insert = []
            for offset, block_dict in enumerate(blocks_data, start=1):
                new_block = Block(
                    chapter_id=chapter_id,
                    reading_order=base_order + (offset * self.READING_ORDER_STEP),
                    block_type=block_dict["block_type"],
                    readable_text=block_dict["readable_text"],
                    review_priority=block_dict.get("review_priority", "normal"),
                    heading_level=block_dict.get("heading_level"),
                    source_markup=block_dict.get("source_markup", ""),
                    caption=block_dict.get("caption", ""),
                    image_file=block_dict.get("image_file", "")
                )
                blocks_to_insert.append(new_block)
            
            await self.repo.bulk_insert_blocks(blocks_to_insert)
            await self.db.commit()
            return len(blocks_to_insert)
        except Exception as e:
            await self.db.rollback()
            raise e