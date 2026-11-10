from app.domains.quizzer.routers.student import router_student_quizz
from app.domains.quizzer.routers.teacher import router_teacher_quizz
from app.domains.quizzer.routers.teacher_v2 import router_teacher_quizz_v2

__all__ = ["router_teacher_quizz", "router_student_quizz", 'router_teacher_quizz_v2']
