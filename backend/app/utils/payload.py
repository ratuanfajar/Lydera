

from pydantic import BaseModel
from app.utils.role import Role

class Payload(BaseModel):
    sub: str
    profile_id: int
    role: Role
    iat: int | None = None
    exp: int | None = None