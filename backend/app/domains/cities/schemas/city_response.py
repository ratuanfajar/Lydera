from pydantic import BaseModel, ConfigDict
from datetime import datetime


class CityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
