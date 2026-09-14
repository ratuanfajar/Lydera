from enum import Enum
from fastapi import Query
from pydantic import BaseModel
from typing import Annotated
from app.domains.quizz.models.quiz_request import QuizRequestStatus

class QuizRequestStudentQueryStatus(str, Enum):
    ALL = "Semua"
    NOT_DONE = "Belum Dikerjakan"
    DONE = "Selesai"

class QuizRequestStudentQuery(BaseModel):
    classroom_id: Annotated[int, Query(...)]
    status: Annotated[QuizRequestStudentQueryStatus | None, Query()] = QuizRequestStudentQueryStatus.ALL

class QuizRequestDetailQuery(BaseModel):
    classroom_id: Annotated[int, Query(...)]