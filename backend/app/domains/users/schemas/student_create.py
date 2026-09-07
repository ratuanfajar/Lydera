from app.utils.role import AllowedRole
from app.domains.users.schemas.user_create import UserCreate
from typing import Literal

class StudentCreate(UserCreate):
    role: Literal[AllowedRole.STUDENT] = AllowedRole.STUDENT