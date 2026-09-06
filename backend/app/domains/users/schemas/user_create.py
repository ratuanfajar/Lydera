from utils.role import Role
from pydantic import BaseModel, EmailStr, Field

class UserCredentials(BaseModel):
    email: EmailStr = Field(
        title="The email",
    )

    password: str = Field(
        min_length=8,
        title="The password",
    )

    role: Role = Field(
        title="The role",
    )
    
class UserCreate(UserCredentials):
    confirm_password: str = Field(
        min_length=8,
        title="The password confirmation",
    )

