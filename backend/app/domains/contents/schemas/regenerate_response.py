from pydantic import BaseModel


class RegenerateResponse(BaseModel):
    block_id: int
    readable_text: str