from datetime import datetime

from pydantic import BaseModel


class ModuleCreate(BaseModel):
    title: str
    fase_id: int


