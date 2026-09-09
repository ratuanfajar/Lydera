from pydantic import BaseModel


class FaseResponse(BaseModel):
    id: int
    kode: str


