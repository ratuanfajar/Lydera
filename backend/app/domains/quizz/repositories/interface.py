from app.domains.quizz.repositories.interfaces.quiz_request_interface import QuizRequestRepositoryInterface
from app.domains.quizz.repositories.interfaces.soal_interface import SoalRepositoryInterface
from app.domains.quizz.repositories.interfaces.quiz_progress_interface import QuizProgressRepositoryInterface

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
