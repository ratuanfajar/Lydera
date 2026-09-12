from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated
import json
from fastapi import APIRouter, HTTPException, File, Form, Query, UploadFile, Depends, status, Body, Path as FastAPIPath
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

# Asumsikan import base response ini sudah Anda miliki di project
from app.core.response import Response, get_response_message, COMMON_VALIDATION_RESPONSES
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.utils import paths
from app.utils.role import Role
from app.tasks.mineru_tasks import process_mineru_job_task
from app.core.exceptions import BadRequestException
from app.domains.contents.schemas.blocks.block_review_response import BlockPreviewResponse
from app.domains.contents.schemas.chapters.ingest_annonated_request import IngestAnnotatedRequest
from app.tasks.progress_tasks import enqueue_module_progress_job
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
        await content_service.update_block_text(block_id, payload.feedback)

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
    teacher : Roles(Role.TEACHER),
    payload: Annotated[ModuleCreate, Body()], 
    service: ContentService = Depends(get_content_service)
):
    try:
        module = await service.create_module(payload.title, payload.description, payload.status, payload.classroom_id, teacher.profile_id, payload.fase_id)
        return Response(
            message=get_response_message(),
            data=module
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router_modules.post(
    "/publish/{module_id}",
    description="Requires the TEACHER role",
    response_model=Response[bool],
    status_code=status.HTTP_200_OK
)
async def publish_module(
    module_id: int,
    teacher: Roles(Role.TEACHER),
    service: ContentService = Depends(get_content_service),
):
    result = await service.publish_module(module_id, teacher.profile_id)
    return Response(
        message="Berhasil publish",
        data=result
    )

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
    file: Annotated[UploadFile, File(description="Single PDF file required")],
    content_service: ContentService = Depends(get_content_service),
    job_service: JobService = Depends(get_job_service)
):
    try:
        if not file.filename or file.filename.strip() == "":
            raise BadRequestException(
                detail="A file must be selected."
            )
        if file.content_type != "application/pdf":
            raise BadRequestException(
                detail="Only PDF files are allowed."
            )
        
        chapter_id = await content_service.validate_and_create_chapter(
            module_id=data.module_id, 
            cp_id=data.cp_id, 
            number=data.number, 
            title=data.title, 
            source_file=file.filename
        )
    except ValueError as e:
        raise BadRequestException(status_code=400, detail=str(e))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = UPLOAD_DIR / f"raw-{chapter_id}.pdf"
    
    content = await file.read()
    raw_path.write_bytes(content)

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
    
    await process_mineru_job_task.kiq(
        job_id=job_id,
        pdf_path=str(raw_path),
        out_dir=str(out_dir),
        chapter_id=chapter_id
    )
    await enqueue_module_progress_job(data.module_id)
    return Response(
        message=get_response_message(),
        data={"chapter_id": chapter_id, "job_id": job_id, "status": "queued"}
    )

# Sementara
@router_chapters.get(
    "/preview",
    description="Requires the TEACHER role.",
    response_model=Response[list[BlockPreviewResponse]],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def preview_chapter(
    annotation_path: Annotated[
        str,
        Query(
            description="Relative path to the annotated JSON file",
            examples=["16/raw-16/auto/annotated.json"],
        ),
    ],
    _: Roles(Role.TEACHER),
    content_service: ContentService = Depends(get_content_service),
):
    return Response(
        message="Chapter preview loaded successfully",
        data=content_service.load_preview(annotation_path)
        )

@router_chapters.post(
    "/confirm/{chapter_id}",
    description="Requires the TEACHER role.",
    response_model=Response[int],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES
)
async def confirm_chapter(
    annotation_path: Annotated[
        IngestAnnotatedRequest,
        Body(
            description="Relative path to the annotated JSON file",
            examples=["16/raw-16/auto/annotated.json"],
        ),
    ],
    chapter_id: int,
    teacher: Roles(Role.TEACHER),
    content_service: ContentService = Depends(get_content_service),
):
    result = await content_service.ingest_annotated_json(annotation_path.annotation_path, chapter_id, teacher.profile_id)
    return Response(
        message="Chapter berhasil disimpan di module",
        data=result
)

@router_chapters.get(""
"/jobs/{job_id}/stream",
response_class=StreamingResponse,
    summary="Stream job progress updates via SSE",
    responses={
        200: {
            "description": "Server-Sent Events (SSE) real-time event stream",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "example": '{"job_id": "09f9ed63", "status": "running", "progress": 50, "message": "Processing batch 1"}\n\n'
                    }
                }
            }
        }
    }
)
async def stream_job_progress(job_id: int):
    """Real-time SSE stream for monitoring MinerU job progress."""
    async def event_generator():
        redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_keepalive=True
        )
        pubsub = redis.pubsub()
        channel_name = f"job_progress:{job_id}"
        
        await pubsub.subscribe(channel_name)

        try:
            while True:
                # Listen for messages with a timeout to allow heartbeat checks
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    # Parse message to stop streaming when complete or failed
                    parsed = json.loads(data)
                    if parsed.get("status") in ("done", "failed"):
                        break

                # Heartbeat to keep HTTP connection alive
                yield ": ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await redis.aclose()

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disables proxy buffering (NGINX)
        }
    )