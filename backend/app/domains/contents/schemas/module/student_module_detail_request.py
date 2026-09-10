from typing import Annotated

from fastapi import Query
from pydantic import BaseModel


class StudentModuleDetailRequest(BaseModel):
    classroom_id: Annotated[
        int,
        Query(
            gt=0, 
            description="ID Class Student",
            examples=[1]
        )
    ]
