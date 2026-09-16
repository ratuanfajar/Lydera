from pydantic import BaseModel

class OtpVerifyResponse(BaseModel):
    reset_token: str
    expires_in_seconds: int = 180