from pydantic import BaseModel, Field
from typing import Annotated

class ClassroomCreate(BaseModel):
    name: Annotated[
        str, 
        Field(min_length=1, max_length=100, description="The name of the classroom", json_schema_extra={"example": "Kelas 10 MIPA 1"})
    ]
    classroom_type_id: Annotated[
        int, 
        Field(gt=0, description="The ID of the classroom type (must be greater than 0)")
    ]
    school_id: Annotated[
        int, 
        Field(gt=0, description="The ID of the school this classroom belongs to")
    ]
    grade: Annotated[
        int, 
        Field(ge=10, le=12, description="The grade level of the classroom (10 to 12)")
    ]
