from typing import Optional

from pydantic import BaseModel

from app.domains.quizzer.schemas.quiz_request_teacher_response import QuestionStimulusResponse


class SoalOpsiResponse(BaseModel):
    label: str
    opsi_text: str


class SoalResponse(BaseModel):
    id: int
    chapter_id: int
    stimulus_id: int | None
    bloom_level: int
    question_text: str
    stimulus: Optional[QuestionStimulusResponse]
    options: list[SoalOpsiResponse]
    correct_option: str
    langkah: list[str]
    kesimpulan: str
    stimulus_text: str | None
    review_status: str
    review_priority: str
    validation_notes: str | None
    source_point: str | None = None
    markup: dict | None = None
