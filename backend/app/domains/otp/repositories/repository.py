from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, select

from app.domains.otp.repositories.interface import OtpRepositoryInterface, ResetTokenRepositoryInterface
from app.core.db import AsyncSession
from app.domains.otp.models.otp import OtpVerificationCode

class OtpRepository(OtpRepositoryInterface):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_otps_by_email(self, email: str) -> None:
        await self.db.execute(delete(OtpVerificationCode).where(OtpVerificationCode.email == email))
        await self.db.commit()

    async def create_otp(self, user_id: int, email: str, code: str, expired_at: datetime) -> OtpVerificationCode:
        otp = OtpVerificationCode(user_id=user_id, email=email, code=code, expired_at=expired_at)
        self.db.add(otp)
        await self.db.commit()
        await self.db.refresh(otp)
        return otp

    async def get_valid_otp(self, email: str, code: str) -> OtpVerificationCode | None:
        now = datetime.now(timezone.utc)
        stmt = select(OtpVerificationCode).where(
            OtpVerificationCode.email == email,
            OtpVerificationCode.code == code,
            OtpVerificationCode.expired_at > now
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_active_otp_by_email(self, email:str) -> OtpVerificationCode | None: 
        now = datetime.now(timezone.utc)
        stmt = select(OtpVerificationCode).where(
            OtpVerificationCode.email == email,
            OtpVerificationCode.expired_at > now
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()        

class ResetTokenRepository(ResetTokenRepositoryInterface):
    def __init__(self, redis: Redis):
        self.redis = redis

    async def store_reset_token(self, token: str, email: str, ttl_seconds: int = 180) -> None:
        await self.redis.setex(name=f"reset_token:{token}", time=ttl_seconds, value=email)

    async def get_email_by_token(self, token: str) -> str | None:
        email = await self.redis.get(f"reset_token:{token}")
        return email if email else None

    async def delete_token(self, token: str) -> None:
        await self.redis.delete(f"reset_token:{token}")