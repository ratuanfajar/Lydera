from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.quizz.models.quiz_request import QuizRequestStatus
from app.domains.quizz.schemas.module_quiz_response import ModuleQuizResponse
from app.domains.quizz.models.quiz_progress import QuizReviewStatus
from app.domains.quizz.schemas.quiz_request_teacher_response import QuestionOptionResponse, QuizRequestQuestionResponse


class QuizRequestStudentProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attempt_count: int
    score: int | None = None
    is_done: bool 
    started_at: datetime | None = None
    completed_at: datetime | None = None
    review_status: QuizReviewStatus
    review_error: str | None = None

class QuizRequestStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    status_published: QuizRequestStatus
    max_duration_minutes: int
    max_retry:int
    start_time: datetime
    end_time: datetime
    
    progress: Optional[QuizRequestStudentProgressResponse] = Field(
        default=None, validation_alias="quiz_progress"
    )

    question_counts: int = 0
    module: ModuleQuizResponse

    @field_validator("progress", mode="before")
    def extract_single_progress(cls, v):
        if isinstance(v, list):
            return v[0] if len(v) > 0 else None
        return v

# Detail
class QuestionStudentSteps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    steps: int = Field(validation_alias="urutan")
    text: str = Field(validation_alias="teks")

class QuestionStimulusStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    readable_text: str

class QuestionAnswerStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    soal_id: int
    selected_option: str
    steps: list[QuestionStudentSteps] = Field(validation_alias="langkah")
    
class QuizRequestQuestionStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    stimulus: Optional[QuestionStimulusStudentResponse]
    question_text: str
    kesimpulan: str
    options: List[QuestionOptionResponse] = Field(validation_alias="opsi")
    answer: QuestionAnswerStudentResponse | None = None

