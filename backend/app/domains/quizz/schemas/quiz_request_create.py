from pydantic import BaseModel, Field


class QuizChapterRequest(BaseModel):
    chapter_id: int
    hots_count: int
    lots_count: int


class QuizRequestCreate(BaseModel):
    classroom_id: int
    module_id: int
    title: str = Field(min_length=1, max_length=255)
    chapters: list[QuizChapterRequest] = Field(min_items=1)

    
