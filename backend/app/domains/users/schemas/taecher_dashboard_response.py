from typing import Any

from pydantic import BaseModel
from app.domains.classrooms.schemas import ClassroomInfoResponse
from app.domains.contents.schemas.module.module_response import ModuleResponse

class TeacherDashboardResponse(BaseModel):
    teacher_email: str
    classroom_info: ClassroomInfoResponse | None = None
    total_modules: int = 0
    total_exams: int = 0
    total_students: int = 0
    newest_modules: list[ModuleResponse]
    newest_exams: list[Any] = []