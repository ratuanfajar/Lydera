from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class QuizSaveStatus(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"


class StimulusCreateRequest(BaseModel):
    readable_text: str
    source_markup: str = ""
    source_reading_order_start: Optional[int] = None
    source_reading_order_end: Optional[int] = None


class SoalDataCreateRequest(BaseModel):
    question_text: str
    options: Dict[str, str]  # e.g., {"A": "...", "B": "..."}
    correct_option: str = Field(..., pattern="^[A-D]$")
    langkah: List[str] = Field(default_factory=list)
    kesimpulan: str
    stimulus: Optional[StimulusCreateRequest] = None
    bloom_level: int = Field(..., ge=1, le=6)
    reading_order_start: int
    reading_order_end: int


class SoalCreateRequest(BaseModel):
    chapter_id: int
    data: SoalDataCreateRequest
    review_priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    validation_notes: Optional[str] = None


class SaveQuizRequestPayload(BaseModel):
    classroom_id: int
    status: QuizSaveStatus
    # items: List[SoalCreateRequest]