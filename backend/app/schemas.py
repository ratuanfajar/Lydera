from datetime import datetime

from pydantic import BaseModel


class ModuleCreate(BaseModel):
    title: str
    fase_id: int


class ModuleOut(BaseModel):
    id: int
    title: str
    fase_id: int | None
    created_at: datetime


class ChapterOut(BaseModel):
    id: int
    module_id: int
    number: int | None
    title: str | None
    source_file: str | None
    cp_id: int | None
    created_at: datetime


class FaseOut(BaseModel):
    id: int
    kode: str


class CpOut(BaseModel):
    id: int
    fase_id: int
    domain: str
    cp_text: str


class ChapterCreateResponse(BaseModel):
    chapter_id: int
    job_id: int
    status: str


class JobStatus(BaseModel):
    chapter_id: int
    job_id: int
    status: str
    error: str | None
    blocks_total: int | None


class BlockOut(BaseModel):
    id: int
    reading_order: int
    block_type: str
    readable_text: str
    review_priority: str
    heading_level: int | None
    source_markup: str | None
    caption: str | None
    image_file: str | None


class RegenerateRequest(BaseModel):
    feedback: str


class RegenerateResponse(BaseModel):
    block_id: int
    readable_text: str
