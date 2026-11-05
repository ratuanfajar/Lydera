from typing import Annotated
from pydantic import BaseModel
from fastapi import Query

class TeacherDashboardRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Student",
            examples=[1]
        )
    ]
    limit: Annotated[
        int | None,
        Query(
            gt=0, 
            description="ID Limit",
            examples=[1]
        )
    ] = None



    