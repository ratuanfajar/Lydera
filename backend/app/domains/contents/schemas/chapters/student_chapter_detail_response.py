from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.contents.schemas.blocks.block_response import BlockResponse

class StudentChapterProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_done: bool = False
    completed_at: datetime | None = None

class StudentChapterDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    number: int | None = None
    chapter_progress: StudentChapterProgressResponse | None = Field(
        default=None, 
        validation_alias="chapter_progress"
    )
    blocks: list[BlockResponse] | None = Field(
            default=None, 
    )

class StudentChapterDetailWithoutProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    number: int | None = None
    blocks: list[BlockResponse] | None = Field(
            default=None, 
    )

class StudentChapterDetailWithoutBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    number: int | None = None
    chapter_progress: StudentChapterProgressResponse | None = Field(
        default=None,
        validation_alias="chapter_progress",
    )

    @field_validator("chapter_progress", mode="before")
    @classmethod
    def extract_chapter_progress(cls, value):
        if isinstance(value, list):
            return value[0] if value else None

        return value
