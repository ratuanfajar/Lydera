from pydantic import BaseModel


class CpResponse(BaseModel):
    id: int
    fase_id: int
    domain: str
    cp_text: str


