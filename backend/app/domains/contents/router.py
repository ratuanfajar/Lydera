from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, File, Form, UploadFile, Depends, status, Body, Path as FastAPIPath

# Asumsikan import base response ini sudah Anda miliki di project
from app.core.response import Response, get_response_message, COMMON_VALIDATION_RESPONSES
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.utils import paths
from app.utils.role import Role
paths.setup()
from app.domains.contents.schemas.chapters.chapter_create import ChapterCreate
import regenerate

from app.domains.contents.schemas import (
    BlockResponse, RegenerateRequest, RegenerateResponse, 
    ChapterCreateResponse, ChapterResponse, FaseResponse, CpResponse, 
    ModuleCreate, ModuleResponse
)
from app.domains.jobs.schemas import JobStatus
from app.domains.contents.depedencies import get_content_service
from app.domains.contents.services import ContentService
from app.domains.jobs.depedencies import get_job_service
from app.domains.jobs.services import JobService
from app.core.config import settings
import app.utils.pdf_cut as pdf_cut

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"

def _find_image(out_dir: Path, image_file: str) -> Path | None:
    if not out_dir.exists():
        return None
    matches = list(out_dir.rglob(image_file))
    return matches[0] if matches else None


# ==========================================
# BLOCKS ROUTER
# ==========================================
router_blocks = APIRouter(prefix="/blocks", tags=["blocks"], route_class=WrappedRoute)

@router_blocks.post(
    "/{block_id}/regenerate",
    response_model=Response[RegenerateResponse],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES
)
async def regenerate_block(
    block_id: Annotated[int, FastAPIPath(title="The ID of the block")], 
    payload: Annotated[RegenerateRequest, Body()],
    content_service: ContentService = Depends(get_content_service),
    job_service: JobService = Depends(get_job_service)
):
    block = await content_service.get_block_by_id(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="blok tidak ditemukan")
    if block.block_type not in ("formula", "table", "image"):
        raise HTTPException(status_code=400, detail=f"regenerasi tidak berlaku untuk block_type={block.block_type}")

    image_path = None
    if block.image_file:
        job = await job_service.get_latest_job_for_chapter(block.chapter_id)
        if job:
            image_path = _find_image(Path(job.out_dir), block.image_file)

    new_text = regenerate.regenerate(
        block.block_type, payload.feedback,
        source_markup=block.source_markup or "",
        image_path=image_path,
        caption=block.caption or "",
    )
    
    await content_service.update_block_text(block_id, new_text)
    
    return Response(
        message=get_response_message(),
        data={"block_id": block_id, "readable_text": new_text}
    )


# ==========================================
# FASE ROUTER
# ==========================================
router_fases = APIRouter(prefix="/fases", tags=["fases"], route_class=WrappedRoute)

@router_fases.get(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[list[FaseResponse]],
    status_code=status.HTTP_200_OK
)
async def list_fase(
    _: Roles(Role.TEACHER),
    service: ContentService = Depends(get_content_service)
    ):
        fases = await service.get_all_fases()
        return Response(
            message=get_response_message(),
            data=fases
        )


# ==========================================
# MODULE ROUTER
# ==========================================
router_modules = APIRouter(prefix="/modules", tags=["modules"], route_class=WrappedRoute)

@router_modules.post(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[ModuleResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def create_module(
    _: Roles(Role.TEACHER),
    payload: Annotated[ModuleCreate, Body()], 
    service: ContentService = Depends(get_content_service)
):
    try:
        module = await service.create_module(payload.title, payload.description, payload.status, payload.classroom_id, payload.fase_id)
        return Response(
            message=get_response_message(),
            data=module
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_modules.get(
    "",
    description="Requires the ADMIN role.",
    response_model=Response[list[ModuleResponse]],
    status_code=status.HTTP_200_OK
)
async def list_modules(
    _: Roles(Role.ADMIN),
    service: ContentService = Depends(get_content_service)
    ):
        modules = await service.get_all_modules()
        return Response(
            message=get_response_message(),
            data=modules
        )


# @router_modules.get(
#     "/{module_id}/cp",
#     response_model=Response[list[CpResponse]],
#     status_code=status.HTTP_200_OK
# )
# async def list_module_cp(
#     module_id: Annotated[int, FastAPIPath(title="The ID of the module")], 
#     service: ContentService = Depends(get_content_service)
# ):
#     try:
#         cps = await service.get_cps_by_module_id(module_id)
#         return Response(
#             message=get_response_message(),
#             data=cps
#         )
#     except ValueError as e:
#         raise HTTPException(status_code=404, detail=str(e))


# ==========================================
# CHAPTER ROUTER
# ==========================================
router_chapters = APIRouter(prefix="/chapters", tags=["chapters"], route_class=WrappedRoute)

@router_chapters.post(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[ChapterCreateResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def create_chapter(
    _: Roles(Role.TEACHER),
    data: Annotated[ChapterCreate, Depends()],
    file: Annotated[UploadFile, File(...)],
    content_service: ContentService = Depends(get_content_service),
    job_service: JobService = Depends(get_job_service)
):
    # if start_page < 0 or end_page < start_page:
    #     raise HTTPException(status_code=400, detail="rentang halaman tidak valid")

    try:
        chapter_id = await content_service.validate_and_create_chapter(
            module_id=data.module_id, 
            cp_id=data.cp_id, 
            number=data.number, 
            title=data.title, 
            source_file=file.filename
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = UPLOAD_DIR / f"raw-{chapter_id}.pdf"
    
    content = await file.read()
    raw_path.write_bytes(content)

    # cut_path = UPLOAD_DIR / f"{chapter_id}.pdf"
    # try:
        # pdf_cut.cut(raw_path, cut_path, start_page, end_page)
    # except ValueError as exc:
    #     raise HTTPException(status_code=400, detail=str(exc)) from exc
    # finally:
    #     raw_path.unlink(missing_ok=True)

    out_dir = Path(settings.OUTPUT_DIR) / str(chapter_id) 
    if out_dir.exists() and any(out_dir.iterdir()):
        raise HTTPException(status_code=409, detail=f"folder output {out_dir} sudah berisi data, tidak aman dipakai ulang")

    try:
        job_id = await job_service.enqueue_job(
            chapter_id=chapter_id, 
            pdf_path=str(raw_path), 
            out_dir=str(out_dir)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Gagal memasukkan job ke antrean")

    return Response(
        message=get_response_message(),
        data={"chapter_id": chapter_id, "job_id": job_id, "status": "queued"}
    )


# @router_chapters.get(
#     "/{chapter_id}",
#     response_model=Response[ChapterResponse],
#     status_code=status.HTTP_200_OK
# )
# async def get_chapter(
#     chapter_id: Annotated[int, FastAPIPath(title="The ID of the chapter")], 
#     service: ContentService = Depends(get_content_service)
# ):
#     chapter = await service.get_chapter_by_id(chapter_id)
#     if chapter is None:
#         raise HTTPException(status_code=404, detail="bab tidak ditemukan")
    
#     return Response(
#         message=get_response_message(),
#         data=chapter
#     )


# @router_chapters.get(
#     "/{chapter_id}/blocks",
#     response_model=Response[list[BlockResponse]],
#     status_code=status.HTTP_200_OK
# )
# async def list_blocks(
#     chapter_id: Annotated[int, FastAPIPath(title="The ID of the chapter")], 
#     service: ContentService = Depends(get_content_service)
# ):
#     blocks = await service.get_blocks_by_chapter(chapter_id)
#     return Response(
#         message=get_response_message(),
#         data=blocks
#     )


# @router_chapters.get(
#     "/{chapter_id}/status",
#     response_model=Response[JobStatus],
#     status_code=status.HTTP_200_OK
# )
# async def get_status(
#     chapter_id: Annotated[int, FastAPIPath(title="The ID of the chapter")], 
#     job_service: JobService = Depends(get_job_service)
# ):
#     job = await job_service.get_latest_job_for_chapter(chapter_id)
#     if job is None:
#         raise HTTPException(status_code=404, detail="belum ada proses untuk bab ini")
    
#     return Response(
#         message=get_response_message(),
#         data={
#             "chapter_id": chapter_id,
#             "job_id": job.id,
#             "status": job.status,
#             "error": job.error,
#             "blocks_total": job.blocks_total,
#         }
#     )
