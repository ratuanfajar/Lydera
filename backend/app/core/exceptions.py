class AppException(Exception):
    status_code = 400
    detail = "Bad request"

    def __init__(
        self,
        detail: str | None = None,
        errors: list | None = None,
    ):
        self.detail = detail if detail is not None else self.__class__.detail
        self.errors = errors

        super().__init__(self.detail)


class NotFoundException(AppException):
    status_code = 404
    detail = "Resource not found"

class BadRequestException(AppException):
    status_code = 400
    detail = "Bad Request"


class ForbiddenException(AppException):
    status_code = 403
    detail = "Forbidden"


class CredentialException(AppException):
    status_code = 401
    detail = "Unauthorized"


class ValidationException(AppException):
    status_code = 422
    detail = "Validation failed"