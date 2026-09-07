from pydantic import BaseModel, Field

class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, title="The name of the school")
    city_id: int = Field(title="The city id")
