import random
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from app.core.security import hash_password
from app.tasks.email_tasks import send_otp_task
from app.core.exceptions import BadRequestException, TooManyRequestException

from app.core.db import AsyncSession
from app.domains.otp.repositories.interface import OtpRepositoryInterface, ResetTokenRepositoryInterface
from app.domains.users.repositories.interface import UserRepositoryInterface

class PasswordResetService:
    def __init__(
        self, 
        otp_repo: OtpRepositoryInterface, 
        token_repo: ResetTokenRepositoryInterface,
        user_repo: UserRepositoryInterface,
        db: AsyncSession,
    ):
        self.otp_repo = otp_repo
        self.token_repo = token_repo
        self.user_repo = user_repo
        self.db = db

    async def request_otp(self, email: str) -> bool:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return True

        existing_otp = await self.otp_repo.get_active_otp_by_email(email)
        if existing_otp:
            raise TooManyRequestException(
                detail="OTP telah dikirim, silahkan check email atau tunggu lagi nanti."
            )
        
        await self.otp_repo.delete_otps_by_email(email)
        otp_code = f"{random.randint(100000, 999999)}"
        expired_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        await self.otp_repo.create_otp(user_id=user.id, email=email, code=otp_code, expired_at=expired_at)
        await self.db.commit()

        await send_otp_task.kiq(to_email=email, otp_code=otp_code)
        return True

    async def verify_otp(self, email: str, code: str) -> str:
        otp_record = await self.otp_repo.get_valid_otp(email, code)
        if not otp_record:
            raise BadRequestException(
                detail="Invalid or expired OTP code"
            )

        await self.otp_repo.delete_otps_by_email(email)
        reset_token = secrets.token_urlsafe(32)
        await self.token_repo.store_reset_token(token=reset_token, email=email, ttl_seconds=180)

        return reset_token

    async def reset_password(self, token: str, new_password: str) -> bool:
        email = await self.token_repo.get_email_by_token(token)

        if not email:
            raise BadRequestException(
                detail="Invalid or expired OTP code"
            )
        
        user = await self.user_repo.get_by_email(email)

        try:
            hashed_pw = hash_password(new_password)
            await self.user_repo.update_password(user_id=user.id, password=hashed_pw)

            await self.token_repo.delete_token(token)

            await self.db.commit()
            return True

        except Exception:
            await self.db.rollback()
            raise