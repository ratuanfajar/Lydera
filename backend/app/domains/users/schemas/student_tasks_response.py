from typing import Any
from pydantic import BaseModel, ConfigDict
from app.domains.contents.schemas.module.student_module_response import StudentModuleResponse, StudentModuleWithoutChaptersResponse
from app.domains.quizz.schemas.quiz_request_student_response import QuizRequestStudentResponse

class StudentTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    modules: list[StudentModuleWithoutChaptersResponse]
    exams: list[QuizRequestStudentResponse]
