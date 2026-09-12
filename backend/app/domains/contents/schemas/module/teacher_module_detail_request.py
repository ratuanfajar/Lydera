from typing import Annotated
from fastapi import Query
from pydantic import BaseModel

class TeacherModuleDetailRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Teacher",
            examples=[1]
        )
    ]