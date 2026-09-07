from app.utils.role import AllowedRole
from app.domains.users.schemas.user_create import UserCreate
from typing import Literal

class TeacherCreate(UserCreate):
    role: Literal[AllowedRole.TEACHER] = AllowedRole.TEACHER
