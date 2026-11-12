import json
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.redis import get_redis_client
from app.core.response import COMMON_VALIDATION_RESPONSES, Response, get_response_message
from app.core.route import WrappedRoute
from app.core.security import Roles
from app.domains.contents.depedencies import get_chapter_service
from app.domains.contents.schemas import ChapterCreateResponse
from app.domains.contents.schemas.blocks.block_review_response import BlockPreviewResponse
from app.domains.contents.schemas.chapters.chapter_create import ChapterCreate
from app.domains.contents.schemas.chapters.ingest_annonated_request import IngestAnnotatedRequest
from app.domains.contents.services.chapter_service import ChapterService
from app.domains.jobs.depedencies import get_job_service
from app.domains.jobs.services import JobService
from app.tasks.mineru_tasks import process_mineru_job_task
from app.tasks.progress_tasks import enqueue_module_progress_job
from app.utils.role import Role

UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads"

router_chapters = APIRouter(prefix="/chapters", tags=["chapters"], route_class=WrappedRoute)


@router_chapters.post(
    "",
    description="Requires the TEACHER role.",
    response_model=Response[ChapterCreateResponse],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
)
async def create_chapter(
    current_user: Roles(Role.TEACHER),
    data: Annotated[ChapterCreate, Depends()],
    file: Annotated[UploadFile, File(description="Single PDF file required")],
    service: ChapterService = Depends(get_chapter_service),
    job_service: JobService = Depends(get_job_service),
):
    try:
        if not file.filename or file.filename.strip() == "":
            raise BadRequestException(detail="A file must be selected.")
        if file.content_type != "application/pdf":
            raise BadRequestException(detail="Only PDF files are allowed.")

        chapter_id = await service.validate_and_create_chapter(
            module_id=data.module_id,
            cp_id=data.cp_id,
            number=data.number,
            title=data.title,
            source_file=file.filename,
        )
    except ValueError as e:
        raise BadRequestException(status_code=400, detail=str(e))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = UPLOAD_DIR / f"raw-{chapter_id}.pdf"

    content = await file.read()
    raw_path.write_bytes(content)

    out_dir = Path(settings.OUTPUT_DIR) / str(chapter_id)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise HTTPException(
            status_code=409,
            detail=f"folder output {out_dir} sudah berisi data, tidak aman dipakai ulang",
        )

    try:
        job_id = await job_service.enqueue_job(
            chapter_id=chapter_id,
            pdf_path=str(raw_path),
            out_dir=str(out_dir),
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Gagal memasukkan job ke antrean")

    await process_mineru_job_task.kiq(
        job_id=job_id,
        pdf_path=str(raw_path),
        out_dir=str(out_dir),
        chapter_id=chapter_id,
        teacher_id=current_user.profile_id,
    )
    await enqueue_module_progress_job(data.module_id)
    return Response(
        message=get_response_message(),
        data={"chapter_id": chapter_id, "job_id": job_id, "status": "queued"},
    )


@router_chapters.get(
    "/preview",
    description="Requires the TEACHER role.",
    response_model=Response[list[BlockPreviewResponse]],
    status_code=status.HTTP_200_OK,
    responses=COMMON_VALIDATION_RESPONSES,
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
    service: ChapterService = Depends(get_chapter_service),
):
    return Response(
        message="Chapter preview loaded successfully",
        data=service.load_preview(annotation_path),
    )


@router_chapters.post(
    "/confirm/{chapter_id}",
    description="Requires the TEACHER role.",
    response_model=Response[int],
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_VALIDATION_RESPONSES,
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
    service: ChapterService = Depends(get_chapter_service),
):
    result = await service.ingest_annotated_json(
        annotation_path.annotation_path,
        chapter_id,
        teacher.profile_id,
    )
    return Response(
        message="Chapter berhasil disimpan di module",
        data=result,
    )


@router_chapters.get(
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
                        "example": (
                            '{"job_id": "09f9ed63", "status": "running", '
                            '"progress": 50, "message": "Processing batch 1"}\n\n'
                        ),
                    }
                }
            },
        }
    },
)
async def stream_job_progress(
    job_id: int,
    ):

    """Real-time SSE stream for monitoring MinerU job progress."""
    async def event_generator():
        redis: Redis = get_redis_client()
        pubsub = redis.pubsub()
        channel_name = f"job_progress:{job_id}"
        state_key = f"job_last_state:{job_id}"

        await pubsub.subscribe(channel_name)

        try:
            last_state = await redis.get(state_key)
            if last_state:
                state_str = (
                    last_state.decode("utf-8")
                    if isinstance(last_state, bytes)
                    else last_state
                )
                yield f"data: {state_str}\n\n"

                parsed_initial = json.loads(state_str)
                if parsed_initial.get("status") in ("done", "failed"):
                    return

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"

                    parsed = json.loads(data)
                    if parsed.get("status") in ("done", "failed"):
                        break

                yield ": ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
