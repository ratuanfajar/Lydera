from pydantic import BaseModel


class RegenerateResponse(BaseModel):
    block_ids: list[int]
    readable_text: str

class RegenerateDetailResponse(BaseModel):
    readable_text: str
    block_id:int