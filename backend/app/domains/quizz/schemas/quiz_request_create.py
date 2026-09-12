from pydantic import BaseModel


class QuizChapterRequest(BaseModel):
    chapter_id: int
    hots_count: int
    lots_count: int


class QuizRequestCreate(BaseModel):
    module_id: int
    chapters: list[QuizChapterRequest]
