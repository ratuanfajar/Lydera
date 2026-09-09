from pydantic import BaseModel

class JobStatus(BaseModel):
    chapter_id: int
    job_id: int
    status: str
    error: str | None
    blocks_total: int | None

