from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.domains.quizzer.models.quiz_request import QuizRequestStatus
from app.domains.quizzer.models.quiz_request_chapter import QuizRequestChapter
from app.domains.quizzer.schemas.module_quiz_response import ModuleQuizResponse

class QuizRequestTeacherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    status_published: QuizRequestStatus
    max_duration_minutes: int
    start_time: datetime
    end_time: datetime
    status: str
    error: Optional[str] = None

    question_counts: int = 0
    module: ModuleQuizResponse

# Detail
class QuestionExplanationSteps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    steps: int = Field(validation_alias="urutan")
    text: str = Field(validation_alias="teks")


class QuizRequestChapterDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quiz_request_id:int
    chapter_id: int
    hots_count: int
    lots_count: int

class QuestionOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    opsi_text: str

class QuestionStimulusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_markup: str
    readable_text: str
    ringkasan: Optional[str] = None
    tabel: Optional[dict] = None
    jenis: str = "teks"
    spesifikasi: Optional[dict] = None
    review_status: str
    source_reading_order_start: int
    source_reading_order_end: int
    
class QuizRequestQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    stimulus: Optional[QuestionStimulusResponse]
    bloom_level: int
    question_text:str
    correct_option: str
    kesimpulan: str
    source_reading_order_start: int
    source_reading_order_end: int
    review_status: str = 'pending'
    review_priority: str ='normal'
    validation_notes: Optional[str]
    source_point: Optional[str] = None
    markup: Optional[dict] = None
    options: List[QuestionOptionResponse] = Field(validation_alias="opsi")
    explanation_steps: List[QuestionExplanationSteps] = Field(validation_alias="langkah")

class QuizRequestTeacherDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    title: str
    status_published: QuizRequestStatus
    status: str
    max_duration_minutes: int
    max_retry:int
    start_time: datetime
    end_time: datetime
    error: Optional[str] = None
    coverage_report: Optional[dict] = None
    questions: List[QuizRequestQuestionResponse] = Field(validation_alias="soals")
    quiz_request_chapters: List[QuizRequestChapterDetailResponse] = Field(validation_alias="chapter_links")
    module: ModuleQuizResponse

