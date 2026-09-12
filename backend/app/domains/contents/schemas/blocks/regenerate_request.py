from pydantic import BaseModel


class RegenerateRequest(BaseModel):

    feedback: str
    block_ids: list[int]