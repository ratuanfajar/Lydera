from pydantic import BaseModel, ConfigDict
from datetime import datetime


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nis: str | None = None
    nisn: str | None = None
    grade: int | None = None
    created_at: datetime
    updated_at: datetime