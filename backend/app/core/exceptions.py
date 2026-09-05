class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)

        
class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)