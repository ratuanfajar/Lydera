from pydantic import BaseModel


class QuizRequestCreateResponse(BaseModel):
    quiz_request_id: int
    status: str


class QuizRequestStatus(BaseModel):
    quiz_request_id: int
    status: str
    error: str | None
