from abc import ABC, abstractmethod

from app.domains.otp.models.otp import OtpVerificationCode

class OtpRepositoryInterface(ABC):
    @abstractmethod
    async def create_otp(self, user_id: int, email: str, code: str, expired_at) -> OtpVerificationCode: raise NotImplementedError
    
    @abstractmethod
    async def get_valid_otp(self, email: str, code: str) -> OtpVerificationCode | None: raise NotImplementedError
    
    @abstractmethod
    async def delete_otps_by_email(self, email: str) -> None: raise NotImplementedError

    @abstractmethod
    async def get_active_otp_by_email(self, email:str) -> OtpVerificationCode | None: raise NotImplementedError

class ResetTokenRepositoryInterface(ABC):
    @abstractmethod
    async def store_reset_token(self, token: str, email: str, ttl_seconds: int = 180) -> None: raise NotImplementedError
    
    @abstractmethod
    async def get_email_by_token(self, token: str) -> str | None: raise NotImplementedError
    
    @abstractmethod
    async def delete_token(self, token: str) -> None: raise NotImplementedError