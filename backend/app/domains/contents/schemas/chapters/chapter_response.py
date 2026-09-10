from datetime import datetime
from pydantic import BaseModel


class ChapterResponse(BaseModel):
    id: int
    module_id: int
    number: int | None
    title: str | None
    source_file: str | None
    cp_id: int | None
    created_at: datetime



