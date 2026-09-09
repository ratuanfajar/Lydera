from datetime import datetime

from pydantic import BaseModel

class ModuleResponse(BaseModel):
    id: int
    title: str
    fase_id: int | None
    created_at: datetime