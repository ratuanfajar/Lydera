from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field

from app.core.response import Response
from app.core.route import WrappedRoute
from app.domains.otp.depedencies import get_reset_password_service
from app.domains.otp.schemas.otp_request import OtpRequest
from app.domains.otp.schemas.otp_verify_request import OtpVerifyRequest
from app.domains.otp.schemas.otp_verify_response import OtpVerifyResponse
from app.domains.otp.schemas.reset_password_request import ResetPasswordRequest
from app.domains.otp.services import PasswordResetService


router_reset_password = APIRouter(prefix="/users", tags=["users"], route_class=WrappedRoute)

@router_reset_password.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(
    payload: OtpRequest, 
    service: PasswordResetService = Depends(get_reset_password_service)
):
    await service.request_otp(email=payload.email)
    return Response(
        message="Otp telah dikirim",
        data=True
    )

@router_reset_password.post("/verify-otp", response_model=Response[OtpVerifyResponse])
async def verify_otp(
    payload: OtpVerifyRequest, 
    service: PasswordResetService = Depends(get_reset_password_service)
):
    token = await service.verify_otp(email=payload.email, code=payload.code)
    return Response(
        message="Berhasil verify token",
        data=OtpVerifyResponse(reset_token=token)
    )

@router_reset_password.post("/reset-password", status_code=status.HTTP_200_OK, response_model=Response[bool])
async def reset_password(
    payload: ResetPasswordRequest, 
    service: PasswordResetService = Depends(get_reset_password_service)
):
    await service.reset_password(token=payload.token, new_password=payload.new_password)
    return Response(
        message="Password berhasil di update",
        data=True
    )