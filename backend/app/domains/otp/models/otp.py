from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String

from app.core.db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

class OtpVerificationCode(Base):
    __tablename__ = "otp_verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String(6), nullable=False, unique=True, index=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    user: Mapped["User"] = relationship(
        back_populates="otp_verification_code",
    )


