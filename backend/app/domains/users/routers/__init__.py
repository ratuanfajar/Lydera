from app.domains.users.routers.auth import router_user
from app.domains.users.routers.student import router_student
from app.domains.users.routers.teacher import router_teacher

__all__ = ["router_user", "router_teacher", "router_student"]
