import asyncio
from pathlib import Path

from sqlalchemy import select

import app.utils.paths as paths

paths.setup()

from annotation import annotation_regenerate

from app.core.db import AsyncSession
from app.core.exceptions import BadRequestException
from app.domains.contents.models import Block, Chapter, Module, ModuleStatus
from app.domains.contents.repositories.interfaces.block_interface import (
    BlockRepositoryInterface,
)
from app.domains.contents.schemas.blocks.regenerate_request import RegenerateRequest
from app.domains.contents.schemas.blocks.regenerate_response import (
    RegenerateDetailResponse,
    RegenerateResponse,
)
from app.tasks.progress_tasks import enqueue_chapter_progress_reset_job


class BlockService:
    def __init__(self, repo: BlockRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def get_block_by_id(self, block_id: int) -> Block | None:
        return await self.repo.get_block_by_id(block_id)

    async def regenerate_text_blocks(
        self,
        dto: RegenerateRequest,
        teacher_id: int,
    ) -> RegenerateResponse:
        blocks = await self.repo.get_teacher_blocks(dto.block_ids, teacher_id)

        for block in blocks:
            if block.block_type not in ("text", "heading"):
                raise BadRequestException(
                    f"Block {block.id} invalid. hanya text/heading"
                )

        update_data = [{"id": b.id, "readable_text": dto.feedback} for b in blocks]

        await self.repo.bulk_update_readable_text(update_data)

        unique_chapter_ids = list(set(b.chapter_id for b in blocks))
        for cid in unique_chapter_ids:
            await enqueue_chapter_progress_reset_job(cid)

        return RegenerateResponse(block_ids=dto.block_ids, readable_text=dto.feedback)

    async def regenerate_special_blocks(
        self,
        dto: RegenerateRequest,
        teacher_id: int,
        job_service,
    ) -> list[RegenerateDetailResponse]:
        blocks = await self.repo.get_teacher_blocks(dto.block_ids, teacher_id)

        for block in blocks:
            if block.block_type in ("text", "heading"):
                raise BadRequestException(
                    f"Block {block.id} merupakan text/heading block. "
                    "gunakan text endpoint"
                )

        chapter_ids = list(set(b.chapter_id for b in blocks))
        jobs = await asyncio.gather(
            *[job_service.get_latest_job_for_chapter(c_id) for c_id in chapter_ids]
        )
        job_map = {c_id: job for c_id, job in zip(chapter_ids, jobs)}

        def run_ai(block, job):
            image_path = (
                self._find_image(Path(job.out_dir), block.image_file)
                if block.image_file and job
                else None
            )
            new_text = annotation_regenerate.regenerate(
                block.block_type,
                dto.feedback,
                source_markup=block.source_markup or "",
                image_path=image_path,
                caption=block.caption or "",
            )
            return {"id": block.id, "readable_text": new_text}

        update_data = await asyncio.gather(
            *[
                asyncio.to_thread(run_ai, block, job_map.get(block.chapter_id))
                for block in blocks
            ]
        )
        await self.repo.bulk_update_readable_text(update_data)

        return [
            RegenerateDetailResponse(
                block_id=item["id"],
                readable_text=item["readable_text"],
            )
            for item in update_data
        ]

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

    def _find_image(self, out_dir: Path, image_file: str) -> Path | None:
        if not out_dir.exists():
            return None
        matches = list(out_dir.rglob(image_file))
        return matches[0] if matches else None
