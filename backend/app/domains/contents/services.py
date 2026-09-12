import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Sequence
from app.domains.contents.models import Block, Fase, Module, Chapter, Cp, ModuleStatus
from app.domains.contents.repositories.interface import ContentRepositoryInterface
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.contents.schemas.chapters.chapter_detail_response import ChapterDetailResponse
from app.core.config import DEFAULT_AI_OUTPUT_DIR
from app.tasks.progress_tasks import enqueue_chapter_progress_reset_job, enqueue_module_progress_job

UNMERGEABLE_TYPES = {"image", "table", "formula"}
MAX_BLOCK_CHARS = 350

PRIORITY_MAP = {"high": 3, "normal": 2, "low": 1}
PRIORITY_REVERSE = {3: "high", 2: "normal", 1: "low"}

class ContentService:
    def __init__(self, repo: ContentRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db
        self.READING_ORDER_STEP = 10

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.repo.get_block_by_id(block_id)

    async def get_all_fases(self) -> Sequence[Fase]:
        return await self.repo.get_all_fases()

    async def publish_module(self, module_id: int, teacher_id:int) -> bool:
        return await self.repo.publish_module(module_id, teacher_id)
    
    async def get_cps_by_module_id(self, module_id: int) -> Sequence[Cp]:
        module = await self.repo.get_module_by_id(module_id)
        if not module:
            raise NotFoundException("modul tidak ditemukan")
        if module.fase_id is None:
            return []
        return await self.repo.get_cps_by_fase_id(module.fase_id)

    async def create_module(self, title: str, description: str, status: ModuleStatus, classroom_id: int, teacher_id:int, fase_id: int | None) -> Module:
        module = await self.repo.create_module_teacher(title, description, status, classroom_id, teacher_id, fase_id)
        if not module:
            raise ForbiddenException(detail="Kelas tidak ditemukan atau Anda tidak memiliki akses.")
        try:
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
                stmt = (
                    select(Module)
                    .join(Chapter, Chapter.module_id == Module.id)
                    .where(Chapter.id == block.chapter_id)
                )
                result = await self.db.execute(stmt)
                module = result.scalar_one_or_none()

                if module and module.status == ModuleStatus.PUBLISH:
                    module.status = ModuleStatus.DRAFT

                await self.db.commit()
                await enqueue_chapter_progress_reset_job(block.chapter_id)
                
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
    
    async def ingest_annotated_json(self, annotated_path: str, chapter_id: int, teacher_id:int) -> int:
        is_owner = await self.repo.verify_chapter_teacher(
            chapter_id=chapter_id,
            teacher_id=teacher_id,
        )

        if not is_owner:
            raise ForbiddenException(
                "You do not have access to this chapter"
            )
        
        try:
            path = DEFAULT_AI_OUTPUT_DIR / annotated_path
            raw_blocks_data = self._load_annotated(path)
            blocks_data = self._combine_annotated_blocks(raw_blocks_data, MAX_BLOCK_CHARS)

            base_order = await self.repo.get_current_max_order(chapter_id)
            blocks_to_insert = []
            for offset, block_dict in enumerate(blocks_data, start=1):
                new_block = Block(
                    chapter_id=chapter_id,
                    reading_order=base_order + (offset * self.READING_ORDER_STEP),
                    block_type=block_dict["block_type"],
                    previous_text=block_dict["readable_text"],
                    readable_text=block_dict["readable_text"],
                    review_priority=block_dict.get("review_priority", "normal"),
                    heading_level=block_dict.get("heading_level"),
                    source_markup=block_dict.get("source_markup", ""),
                    caption=block_dict.get("caption", ""),
                    image_file=block_dict.get("image_file", "")
                )
                blocks_to_insert.append(new_block)
            
            await self.repo.bulk_insert_blocks(blocks_to_insert)
            chapter = await self.db.get(Chapter, chapter_id)
            if chapter and chapter.module_id:
                module = await self.db.get(Module, chapter.module_id)
                if module and module.status == ModuleStatus.PUBLISH:
                    module.status = ModuleStatus.DRAFT

            await self.db.commit()

            if chapter and chapter.module_id:
                await enqueue_module_progress_job(chapter.module_id)
                await enqueue_chapter_progress_reset_job(chapter_id)

            return len(blocks_to_insert)
        except Exception as e:
            await self.db.rollback()
            raise e
        
    def load_preview(self, annotated_path:str):
        path = DEFAULT_AI_OUTPUT_DIR / annotated_path
        raw_blocks_data = self._load_annotated(path)
        blocks_data = self._combine_annotated_blocks(raw_blocks_data, MAX_BLOCK_CHARS)
        return blocks_data

    @staticmethod
    def _load_annotated(annotated_path:str):
        raw_blocks_data = json.loads(Path(annotated_path).read_text(encoding="utf-8"))
        return raw_blocks_data
    
    def _combine_annotated_blocks(self, blocks: List[Dict[str, Any]], max_chars: int = MAX_BLOCK_CHARS) -> List[Dict[str, Any]]:
        combined_results: List[Dict[str, Any]] = []
        buffer: List[Dict[str, Any]] = []
        current_char_count: int = 0
        min_heading_level:int | None = None

        def flush_buffer():
            nonlocal buffer, current_char_count, min_heading_level
            if not buffer:
                return
            
            has_heading = any(b.get("block_type") == "heading" for b in buffer)
            aggregated_type = "heading" if has_heading else "text"

            combined_text = "\n\n".join(b.get("readable_text", "").strip() for b in buffer if b.get("readable_text"))
            combined_markup = "\n".join(b.get("source_markup", "").strip() for b in buffer if b.get("source_markup"))

            max_prio_val = max(PRIORITY_MAP.get(b.get("review_priority", "low"), 1) for b in buffer)

            first_block = buffer[0]
            merged_block = {
                "block_type": aggregated_type,
                "reading_order": first_block.get("reading_order"),
                "page": first_block.get("page"),
                "readable_text": combined_text,
                "review_priority": PRIORITY_REVERSE.get(max_prio_val, "low"),
                "heading_level": min_heading_level,
                "source_markup": combined_markup,
                "caption": "",
                "image_file": ""
            }

            combined_results.append(merged_block)
            buffer = []
            current_char_count = 0
            min_heading_level = None

        for block in blocks:
            b_type = block.get("block_type", "")
            b_heading = block.get("heading_level")
            b_text = block.get("readable_text", "")
            text_len = len(b_text)

            # Rule 0: Standalone types (image, table, formula) cannot be combined
            if b_type in UNMERGEABLE_TYPES:
                flush_buffer()
                combined_results.append(block)
                continue

            # Rule 1: Split on new equal or higher levle headings
            if b_heading is not None:
                if min_heading_level is not None and b_heading <= min_heading_level:
                    flush_buffer()

            # Rule 2: Split if adding text exceeds character capacity limit
            if buffer and (current_char_count + text_len > max_chars):
                flush_buffer()

            buffer.append(block)
            current_char_count += text_len

            if b_heading is not None:
                if min_heading_level is None or b_heading < min_heading_level:
                    min_heading_level = b_heading

        flush_buffer()
        return combined_results
        