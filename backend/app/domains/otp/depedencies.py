from fastapi import Depends
from app.core.db import AsyncSession, get_db
from app.domains.otp.repositories.repository import OtpRepository, ResetTokenRepository
from app.domains.otp.services import PasswordResetService
from app.domains.users.depedencies import get_user_repository
from app.domains.users.repositories.repository import UserRepository

def get_otp_repository(db: AsyncSession = Depends(get_db)) -> OtpRepository:
    return OtpRepository(db)

def get_reset_token_repository(db: AsyncSession = Depends(get_db)) -> ResetTokenRepository:
    return ResetTokenRepository(db)

def get_reset_password_service(otp_repo: OtpRepository = Depends(get_otp_repository), reset_token_repo: ResetTokenRepository = Depends(get_reset_token_repository), user_repo: UserRepository = Depends(get_user_repository), db: AsyncSession = Depends(get_db)) -> PasswordResetService:
    return PasswordResetService(otp_repo, reset_token_repo, user_repo, db)