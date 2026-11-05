from app.domains.quizzer.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizzer.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizzer.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface
from app.domains.contents.models import Block, Chapter, Module
from app.domains.quizzer.models import QuizRequest, QuizRequestChapter, Soal, SoalStimulus
from app.domains.quizzer.schemas.quiz_request_query import QuizRequestQueryStatus
from app.domains.quizzer.schemas.quiz_request_create import QuizChapterRequest
from app.domains.quizzer.schemas.soal_create_request import SoalCreateRequest
from app.domains.quizzer.schemas.quiz_request_student_query import QuizRequestStudentQueryStatus
from app.domains.quizzer.models import QuizRequest, QuizRequestChapter, Soal, SoalJawaban, SoalStimulus
from app.domains.quizzer.models.quiz_progress import QuizProgress

# Backward compat alias
QuizRepositoryInterface = type(
    "QuizRepositoryInterface",
    (QuizRequestRepositoryInterface, SoalRepositoryInterface, QuizProgressRepositoryInterface),
    {}
)

__all__ = [
    "QuizRequestRepositoryInterface",
    "SoalRepositoryInterface",
    "QuizProgressRepositoryInterface",
    "QuizRepositoryInterface",
]
