from enum import Enum
from fastapi import Query
from pydantic import BaseModel
from typing import Annotated
from app.domains.quizz.models.quiz_request import QuizRequestStatus

class QuizRequestQueryStatus(str, Enum):
    ALL = "Semua"
    DRAFT = QuizRequestStatus.DRAFT.value
    PUBLISH = QuizRequestStatus.PUBLISH.value

class QuizRequestQuery(BaseModel):
    classroom_id: Annotated[int, Query(...)]
    status: Annotated[QuizRequestQueryStatus | None, Query()] = QuizRequestQueryStatus.ALL

class QuizRequestDetailQuery(BaseModel):
    classroom_id: Annotated[int, Query(...)]