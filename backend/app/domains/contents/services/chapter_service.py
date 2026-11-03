import json
import math
from pathlib import Path
from sqlalchemy import select

from app.core.config import DEFAULT_AI_OUTPUT_DIR
from app.core.db import AsyncSession
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.domains.contents.models import Block, Chapter, Module, ModuleStatus
from app.domains.contents.repositories.interfaces.content_interface import ContentRepositoryInterface
from app.domains.contents.repositories.interfaces.module_interface import ModuleRepositoryInterface
from app.domains.contents.schemas.blocks.block_response import BlockResponse
from app.domains.contents.schemas.chapters.chapter_detail_response import ChapterDetailResponse
from app.domains.contents.schemas.chapters.student_chapter_detail_response import (
    BlockPaginationMeta,
    StudentChapterDetailV2Response,
    StudentChapterDetailWithoutProgressResponse,
)
from app.tasks.progress_tasks import enqueue_chapter_progress_reset_job, enqueue_module_progress_job

UNMERGEABLE_TYPES = {"image", "table", "formula"}
MAX_BLOCK_CHARS = 350
PRIORITY_MAP = {"high": 3, "normal": 2, "low": 1}
PRIORITY_REVERSE = {3: "high", 2: "normal", 1: "low"}

class ChapterService:
    def __init__(self, repo: ContentRepositoryInterface, module_repo: ModuleRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.module_repo = module_repo
        self.db = db
        self.READING_ORDER_STEP = 10

    async def get_chapter_by_id(self, chapter_id: int, teacher_id: int) -> ChapterDetailResponse:
        chapter = await self.repo.get_chapter_by_id(chapter_id, teacher_id)
        if not chapter:
            raise ForbiddenException("Tidak mempunyai akses atau tidak ada")
        return ChapterDetailResponse.model_validate(chapter)

    async def validate_and_create_chapter(self, module_id: int, cp_id: int | None, number: int | None, title: str | None, source_file: str) -> int:
        try:
            module = await self.module_repo.get_module_by_id(module_id)
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

    async def ingest_annotated_json(self, annotated_path: str, chapter_id: int, teacher_id: int) -> int:
        is_owner = await self.repo.verify_chapter_teacher(
            chapter_id=chapter_id,
            teacher_id=teacher_id,
        )

        if not is_owner:
            raise ForbiddenException("You do not have access to this chapter")

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

    def load_preview(self, annotated_path: str):
        path = DEFAULT_AI_OUTPUT_DIR / annotated_path
        raw_blocks_data = self._load_annotated(path)
        blocks_data = self._combine_annotated_blocks(raw_blocks_data, MAX_BLOCK_CHARS)
        return blocks_data

    async def start_chapter(self, student_id: int, chapter_id: int) -> StudentChapterDetailWithoutProgressResponse:
        has_access = await self.repo.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException(detail="Anda tidak memiliki akses ke chapter ini.")

        chapter = await self.repo.student_get_blocks_by_chapter_id(chapter_id=chapter_id, student_id=student_id)
        if not chapter:
            raise NotFoundException(detail="Chapter tidak ditemukan.")
        await self.repo.student_create_chapter_progress(student_id, chapter_id)
        await self.db.commit()
        return StudentChapterDetailWithoutProgressResponse.model_validate(chapter)

    async def start_chapter_v2(
        self, student_id: int, chapter_id: int, page: int = 1, per_page: int = 10
    ) -> StudentChapterDetailV2Response:
        has_access = await self.repo.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException(detail="Anda tidak memiliki akses ke chapter ini.")

        offset = (page - 1) * per_page
        chapter, blocks, total_blocks = await self.repo.student_get_paginated_blocks(
            chapter_id=chapter_id,
            student_id=student_id,
            limit=per_page,
            offset=offset,
        )
        if not chapter:
            raise NotFoundException(detail="Chapter tidak ditemukan.")

        await self.repo.student_create_chapter_progress(student_id, chapter_id)
        await self.db.commit()

        total_pages = math.ceil(total_blocks / per_page) if total_blocks > 0 else 0

        return StudentChapterDetailV2Response(
            id=chapter.id,
            title=chapter.title,
            number=chapter.number,
            blocks=[BlockResponse.model_validate(b) for b in blocks],
            pagination=BlockPaginationMeta(
                page=page,
                per_page=per_page,
                total_blocks=total_blocks,
                total_pages=total_pages,
            ),
        )

    async def mark_chapter_as_completed(self, student_id: int, chapter_id: int) -> bool:
        has_access = await self.repo.validate_student_chapter_access(chapter_id, student_id)
        if not has_access:
            raise ForbiddenException("Anda tidak memiliki akses ke chapter ini.")

        updated = await self.repo.student_update_chapter_progress(student_id=student_id, chapter_id=chapter_id)

        if not updated:
            raise NotFoundException(detail="Progres chapter tidak ditemukan.")
        await self.db.commit()
        return True

    @staticmethod
    def _load_annotated(annotated_path: str):
        raw_blocks_data = json.loads(Path(annotated_path).read_text(encoding="utf-8"))
        return raw_blocks_data

    def _combine_annotated_blocks(self, blocks: list[dict], max_chars: int = MAX_BLOCK_CHARS) -> list[dict]:
        combined_results: list[dict] = []
        buffer: list[dict] = []
        current_char_count: int = 0
        min_heading_level: int | None = None

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

            if b_type in UNMERGEABLE_TYPES:
                flush_buffer()
                combined_results.append(block)
                continue

            if b_heading is not None:
                if min_heading_level is not None and b_heading <= min_heading_level:
                    flush_buffer()

            if buffer and (current_char_count + text_len > max_chars):
                flush_buffer()

            buffer.append(block)
            current_char_count += text_len

            if b_heading is not None:
                if min_heading_level is None or b_heading < min_heading_level:
                    min_heading_level = b_heading

        flush_buffer()
        return combined_results
