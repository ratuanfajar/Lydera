from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.contents.schemas.blocks.block_response import BlockResponse

class StudentChapterProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_done: bool = False
    completed_at: datetime | None = None

class StudentChapterDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    number: int
    chapter_progress: StudentChapterProgressResponse | None = Field(
        default=None, 
        validation_alias="chapter_progress"
    )
    blocks: list[BlockResponse] | None = Field(
            default=None, 
    )
