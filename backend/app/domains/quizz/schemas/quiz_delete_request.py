from pydantic import BaseModel

class QuizDeleteRequest(BaseModel):
    classroom_id: int