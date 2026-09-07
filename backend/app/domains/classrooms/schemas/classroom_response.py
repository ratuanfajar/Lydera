from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.domains.classrooms.schemas.classroom_type_response import ClassroomTypeResponse


class ClassroomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    school_id: int
    name: str
    code: str
    grade: int
    classroom_type: ClassroomTypeResponse
    created_at: datetime
    updated_at: datetime
