from typing import Annotated, Optional
from fastapi import Body
from pydantic import BaseModel

class RecordNoteCreate(BaseModel):

    title: Annotated[
        Optional[str],
        Body(
            description='Title Note',
            examples=['Circle']
        )
    ] = None

    content: Annotated[
        Optional[str],
        Body(
            description='Content Note',
            examples=['Formula of circle is PI times two']
        )
    ]

    chapter_id: Annotated[
        int,
        Body(
            gt=0, 
            description="Chapter id",
            examples=[1]
        )
    ]