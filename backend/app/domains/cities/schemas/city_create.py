from pydantic import BaseModel, Field

class CityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, title="The name of the city")