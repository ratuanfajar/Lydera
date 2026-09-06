from pydantic import BaseModel, EmailStr
from domains.users.schemas.teacher_response import TeacherResponse
from domains.users.schemas.student_response import StudentResponse

class ProfileResponse(BaseModel):
    user_id: int
    email: EmailStr
    teacher: TeacherResponse | None = None
    student: StudentResponse | None = None