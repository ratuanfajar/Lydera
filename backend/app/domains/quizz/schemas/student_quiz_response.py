from pydantic import BaseModel, ConfigDict

from app.domains.users.schemas.profile_response import ProfileResponse
from app.domains.quizz.schemas.quiz_request_student_response import QuizRequestStudentProgressResponse


class StudentQuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    student_profile: ProfileResponse
    quiz: QuizRequestStudentProgressResponse | None = None
