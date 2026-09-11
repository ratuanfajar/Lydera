from pydantic import BaseModel
from app.domains.classrooms.schemas import ClassroomInfoResponse

class StudentDashboardResponse(BaseModel):
    student_email: str
    classroom_info: ClassroomInfoResponse | None = None
    modules_not_done: int = 0
    exam_not_done: int = 0