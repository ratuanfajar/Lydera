from pydantic import BaseModel


class RegenerateRequest(BaseModel):
    feedback: str