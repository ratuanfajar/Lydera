from app.utils.role import AllowedRole
from pydantic import BaseModel, EmailStr, Field, model_validator

class UserCredentials(BaseModel):
    email: EmailStr = Field(
        title="The email",
    )

    password: str = Field(
        min_length=8,
        title="The password",
    )

    role: AllowedRole = Field(
        title="The role",
    )
    
class UserCreate(UserCredentials):
    confirm_password: str = Field(
        min_length=8,
        title="The password confirmation",
    )

    @model_validator(mode="after")
    def verify_password_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

