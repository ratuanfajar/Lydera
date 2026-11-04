from app.domains.contents.routers.block import router_blocks
from app.domains.contents.routers.chapter import router_chapters
from app.domains.contents.routers.cp import router_cps
from app.domains.contents.routers.fase import router_fases
from app.domains.contents.routers.module import router_modules
from app.domains.contents.routers.student import router_student_contents
from app.domains.contents.routers.student_v2 import router_student_contents_v2
from app.domains.contents.routers.teacher import router_teacher_contents

__all__ = [
    "router_blocks",
    "router_chapters",
    "router_cps",
    "router_fases",
    "router_modules",
    "router_student_contents",
    "router_student_contents_v2",
    "router_teacher_contents",
]
