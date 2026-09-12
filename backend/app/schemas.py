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


class QuizChapterRequest(BaseModel):
    chapter_id: int
    hots_count: int
    lots_count: int


class QuizRequestCreate(BaseModel):
    module_id: int
    chapters: list[QuizChapterRequest]


class QuizRequestCreateResponse(BaseModel):
    quiz_request_id: int
    status: str


class QuizRequestStatus(BaseModel):
    quiz_request_id: int
    status: str
    error: str | None


class SoalOpsiOut(BaseModel):
    label: str
    opsi_text: str


class SoalOut(BaseModel):
    id: int
    chapter_id: int
    stimulus_id: int | None
    bloom_level: int
    question_text: str
    options: list[SoalOpsiOut]
    correct_option: str
    langkah: list[str]
    kesimpulan: str
    stimulus_text: str | None
    review_status: str
    review_priority: str
    validation_notes: str | None


class SoalEditRequest(BaseModel):
    question_text: str | None = None
    options: dict[str, str] | None = None
    correct_option: str | None = None
    langkah: list[str] | None = None
    kesimpulan: str | None = None


class SoalRegenerateRequest(BaseModel):
    feedback: str


class SoalStatusResponse(BaseModel):
    id: int
    review_status: str
