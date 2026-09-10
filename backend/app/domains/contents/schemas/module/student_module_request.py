from typing import Annotated
from enum import Enum
from fastapi import Query
from pydantic import BaseModel

class StudentModuleStatus(str, Enum):
    ALL = "Semua", 
    DONE = "Selesai",
    NOT_DONE = "Belum Selesai"

class StudentModuleRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Student",
            examples=[1]
        )
    ]

    status: Annotated[
        StudentModuleStatus,
        Query(
            default=StudentModuleStatus.ALL,
            examples=[StudentModuleStatus.ALL],
            description="Filter tasks by status: 'Semua', 'Belum Selesai', or 'Selesai'"
        )
    ]