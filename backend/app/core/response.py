from typing import Generic, TypeVar, Any
from contextvars import ContextVar
from pydantic import BaseModel, Field
from core.exceptions import CredentialException, ForbiddenException

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    message: str
    data: T

_response_message: ContextVar[str] = ContextVar("_response_message", default="success")

def set_response_message(message: str) -> None:
    _response_message.set(message)

def get_response_message() -> str:
    return _response_message.get()

class ErrorResponse(BaseModel):
    detail: str
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        examples=[None],
    )

class ValidationErrorResponse(BaseModel):
    detail: str
    errors: list[dict[str, Any]]

COMMON_AUTH_RESPONSES = {
    CredentialException.status_code: {
        "model": ErrorResponse,
        "description": CredentialException.message,
    },
    ForbiddenException.status_code: {
        "model": ErrorResponse,
        "description": ForbiddenException.message,
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "Validation failed",
    },
}

COMMON_VALIDATION_RESPONSES = {
    422: {
        "model": ValidationErrorResponse,
        "description": "Validation failed",
    },
}