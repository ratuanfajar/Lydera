

from app.domains.contents.schemas.chapters.chapter_response import ChapterResponse
from app.domains.contents.schemas.blocks.block_response import BlockResponse
from app.domains.jobs.schemas.job_response import JobResponse


class ChapterDetailResponse(ChapterResponse):
    job: JobResponse | None = None
    blocks: list[BlockResponse]