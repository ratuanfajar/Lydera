from typing import Annotated
from pydantic import BaseModel
from fastapi import Query
from enum import Enum
class StudentTaskStatus(str, Enum):
    ALL = "Semua", 
    MODULE = "Materi",
    EXAM = "Soal Ujian"

class StudentDashboardRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Student",
            examples=[1]
        )
    ]


    