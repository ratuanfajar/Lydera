from pydantic import BaseModel
from app.domains.classrooms.schemas import ClassroomStudentResponse

class StudentDashboardResponse(BaseModel):
    student_email: str
    classroom_info: ClassroomStudentResponse | None = None
    modules_not_done: int = 0
    exam_not_done: int = 0