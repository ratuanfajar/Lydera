from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field



class QuizEditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    max_duration_minutes: Optional[int] = Field(
        None, gt=0, description="Durasi pengerjaan dalam menit (> 0)"
    )
    max_retry: Optional[int] = Field(
        None, gt=0, description="Durasi pengerjaan dalam menit (> 0)"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
