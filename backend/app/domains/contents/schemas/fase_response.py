from pydantic import BaseModel, ConfigDict


class FaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode: str


