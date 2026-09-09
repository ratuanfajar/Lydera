from pydantic import BaseModel

class ChapterCreateResponse(BaseModel):
    chapter_id: int
    job_id: int
    status: str


