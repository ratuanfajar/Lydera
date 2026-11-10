from pydantic import BaseModel, ConfigDict


class QuizRequestCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    quiz_request_id: int
    status: str
    idem_key: str | None = None
    is_cached: bool = False


class QuizRequestStatus(BaseModel):
    quiz_request_id: int
    status: str
    error: str | None
