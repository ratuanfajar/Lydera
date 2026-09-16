from pydantic import BaseModel, EmailStr


class OtpRequest(BaseModel):
    email: EmailStr

