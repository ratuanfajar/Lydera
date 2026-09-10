from datetime import datetime

from pydantic import BaseModel, ConfigDict

class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    fase_id: int | None
    created_at: datetime