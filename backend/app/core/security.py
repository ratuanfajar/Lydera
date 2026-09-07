from fastapi import Depends
from pydantic import ValidationError

from app.utils.role import Role
from app.utils.payload import Payload
from app.core.config import settings
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from app.core.exceptions import CredentialException, ForbiddenException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

password_hash = PasswordHash.recommended()

bearer_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password:str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str :
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(
            days=settings.ACCESS_TOKEN_EXPIRE_DAY
        )
    expire = now + expires_delta
    to_encode = data.copy()
    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    })
    return jwt.encode(
        to_encode,
        settings.APP_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

def decode_access_token(token : str) -> Payload:
    try:
        payload_dict = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return Payload.model_validate(payload_dict)
    except Exception as e:
        print(f"ERROR JWT DECODE: {repr(e)}")
        raise CredentialException

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Payload:
    token = credentials.credentials
    return decode_access_token(token)


CurrentUser = Annotated[
    Payload,
    Depends(verify_token),
]

def require_roles(*allowed_roles: Role):
    async def dependency(
        current_user: CurrentUser,
    ) -> Payload:
        if current_user.role not in allowed_roles:
            raise ForbiddenException
        return current_user
    return dependency

def Roles(*roles: Role):
    return Annotated[
        Payload,
        Depends(require_roles(*roles)),
    ]
