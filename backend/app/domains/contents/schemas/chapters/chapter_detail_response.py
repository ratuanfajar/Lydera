

from app.domains.contents.schemas.chapters.chapter_response import ChapterResponse
from app.domains.contents.schemas.blocks.block_response import BlockResponse


class ChapterDetailResponse(ChapterResponse):
    blocks: list[BlockResponse]