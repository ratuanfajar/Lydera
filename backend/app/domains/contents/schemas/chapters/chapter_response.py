from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ChapterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    module_id: int
    number: int | None
    title: str | None
    source_file: str | None
    cp_id: int | None
    created_at: datetime



