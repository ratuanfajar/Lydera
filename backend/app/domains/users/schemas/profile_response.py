from pydantic import BaseModel, ConfigDict, EmailStr
from app.domains.users.schemas.teacher_response import TeacherResponse
from app.domains.users.schemas.student_response import StudentResponse

class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    teacher: TeacherResponse | None = None
    student: StudentResponse | None = None