from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.domains.quizz.models.quiz_request import QuizRequestStatus
from app.domains.quizz.models.quiz_request_chapter import QuizRequestChapter




class ModuleQuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str  # Module title (name)
    description: str  # Module description


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
    start_time: datetime
    end_time: datetime
    error: Optional[str] = None
    questions: List[QuizRequestQuestionResponse] = Field(validation_alias="soals")
    quiz_request_chapters: List[QuizRequestChapterDetailResponse] = Field(validation_alias="chapter_links")
    module: ModuleQuizResponse

