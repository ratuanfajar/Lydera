class AppException(Exception):
    status_code = 400
    message = "Bad request"

    def __init__(
        self,
        message: str | None = None,
        errors: list | None = None,
    ):
        self.message = message
        self.errors = errors

        super().__init__(self.message)


class NotFoundException(AppException):
    status_code = 404
    message = "Resource not found"


class ForbiddenException(AppException):
    status_code = 403
    message = "Forbidden"


class CredentialException(AppException):
    status_code = 401
    message = "Unauthorized"


class ValidationException(AppException):
    status_code = 422
    message = "Validation failed"