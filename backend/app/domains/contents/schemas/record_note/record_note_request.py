from typing import Annotated
from fastapi import Query
from pydantic import BaseModel

class RecordNoteRequest(BaseModel):
    chapter_id: Annotated[
        int,
        Query(
            gt=0, 
            description="Chapter id",
            examples=[1]
        )
    ]