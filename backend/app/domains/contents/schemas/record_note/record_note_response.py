from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domains.contents.models.module import ModuleStatus

class RecordNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str | None
    content: str
    chapter_id: int
    updated_at: datetime
    created_at: datetime