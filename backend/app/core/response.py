from pydantic import BaseModel
from typing import Generic, TypeVar
from contextvars import ContextVar

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    message: str
    data: T

_response_message: ContextVar[str] = ContextVar("_response_message", default="success")

def set_response_message(message: str) -> None:
    _response_message.set(message)

def get_response_message() -> str:
    return _response_message.get()