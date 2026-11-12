import asyncio
from pathlib import Path

from sqlalchemy import select

import app.utils.paths as paths
from app.domains.contents.schemas.blocks.block_edit import BlockEditRequest, BlockEditResponse

paths.setup()
from annoter import annoter_regenerate
from common.speakable import manual_reading_issues

from app.core.db import AsyncSession
from app.core.exceptions import BadRequestException, NotFoundException
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

DECORATIVE_KIND = "dekoratif"
ILLUSTRATION_KIND = "ilustrasi_konteks"
CONTEXT_TYPES = {"text", "heading"}
class BlockService:
    def __init__(self, repo: BlockRepositoryInterface, db: AsyncSession):
        self.repo = repo
        self.db = db

    async def delete_block_by_id(self, block_id: int):
        block = await self.repo.get_block_by_id(block_id)
        if not block:
            raise NotFoundException(
                f"Block {block_id} tidak ditemukan"
            )
        
        await self.repo.delete_block(block)

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
        await self._resetChapterProgress(blocks)

        return RegenerateResponse(block_ids=dto.block_ids, readable_text=dto.feedback)

    async def _image_context(self, block: Block) -> str:
        limit = annoter_regenerate.IMAGE_CONTEXT_CHARS
        neighbors = await self.repo.get_neighbor_blocks(block.chapter_id, block.reading_order)
        texts = [
            n.readable_text[-limit:] if n.reading_order < block.reading_order else n.readable_text[:limit]
            for n in neighbors if n.block_type in CONTEXT_TYPES and n.readable_text
        ]
        return " ".join(texts)

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
        contexts = {block.id: await self._image_context(block) for block in blocks if block.block_type == "image"}

        def run_ai(block, job):
            image_path = self._find_image(Path(job.out_dir), block.image_file) if block.image_file and job else None
            regenerated = annoter_regenerate.regenerate(
                block.block_type, dto.feedback,
                source_markup=block.source_markup or "",
                image_path=image_path,
                caption=block.caption or "",
                context=contexts.get(block.id, ""),
            )
            image_kind = ILLUSTRATION_KIND if block.image_kind == DECORATIVE_KIND else block.image_kind
            return {
                "id": block.id, "readable_text": regenerated.text, "image_kind": image_kind,
                "ringkasan": regenerated.ringkasan, "tabel": regenerated.tabel,
                "review_priority": "high" if regenerated.issues else block.review_priority,
            }

        update_data = await asyncio.gather(*[
                    asyncio.to_thread(run_ai, block, job_map.get(block.chapter_id)) for block in blocks
                ])
        
        await self.repo.bulk_update_readable_text(update_data)
        await self._resetChapterProgress(blocks)

        return [
            RegenerateDetailResponse(
                block_id=item["id"], 
                readable_text=item["readable_text"], 
                ringkasan=item["ringkasan"], 
                tabel=item["tabel"],
                review_priority=item["review_priority"],
            )
            for item in update_data
        ]

    async def _resetChapterProgress(self, blocks: list[Block]):
        unique_chapter_ids = list(set(b.chapter_id for b in blocks))
        for cid in unique_chapter_ids:
            await enqueue_chapter_progress_reset_job(cid)
    

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

    async def edit_block(self, block_id: int, teacher_id: int, payload: BlockEditRequest) -> BlockEditResponse:
        """Edit langsung satu blok; bacaan blok khusus diturunkan ulang dari sumber, atau memakai readable_text guru apa adanya."""
        (block,) = await self.repo.get_teacher_blocks([block_id], teacher_id)
        if block.block_type in ("text", "heading"):
            if payload.readable_text is None or not payload.readable_text.strip():
                raise BadRequestException("blok teks atau heading: kirim readable_text tidak kosong")
            problems = manual_reading_issues(payload.readable_text)
            if problems:
                raise BadRequestException(" ".join(problems))
            changes = {"readable_text": payload.readable_text.strip(), "review_priority": "normal"}
            issues: list[str] = []
        else:
            try:
                edited = await asyncio.to_thread(
                    annoter_regenerate.edit, block.block_type,
                    readable_text=payload.readable_text, source_markup=payload.source_markup, tabel=payload.tabel,
                )
            except ValueError as exc:
                raise BadRequestException(str(exc))
            issues = edited.issues
            changes = {"readable_text": edited.text, "review_priority": "high" if issues else "normal"}
            if edited.source_markup is not None:
                changes["source_markup"] = edited.source_markup
            if edited.tabel is not None:
                changes.update(tabel=edited.tabel, ringkasan=edited.ringkasan)
        await self.repo.bulk_update_readable_text([{"id": block.id, **changes}])
        await enqueue_chapter_progress_reset_job(block.chapter_id)

        return BlockEditResponse(
            block_id=block.id, block_type=block.block_type, readable_text=changes["readable_text"],
            source_markup=changes.get("source_markup", block.source_markup), ringkasan=changes.get("ringkasan", block.ringkasan),
            tabel=changes.get("tabel", block.tabel), review_priority=changes["review_priority"], issues=issues,
        )
    
    def _find_image(self, out_dir: Path, image_file: str) -> Path | None:
        if not out_dir.exists():
            return None
        matches = list(out_dir.rglob(image_file))
        return matches[0] if matches else None
