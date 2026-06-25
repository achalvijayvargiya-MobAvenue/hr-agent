"""
Centralised exception hierarchy for HR Agent.

All domain errors subclass HRAgentError so that a single FastAPI exception
handler can return a uniform JSON error shape:

    {
        "error":       "NOT_FOUND",
        "message":     "Job 'abc' not found.",
        "status_code": 404,
        "path":        "/jobs/abc"
    }
"""


class HRAgentError(Exception):
    """Base exception for all HR Agent domain errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code


class NotFoundError(HRAgentError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message)


class ValidationError(HRAgentError):
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation error.") -> None:
        super().__init__(message)


class ConflictError(HRAgentError):
    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, message: str = "Resource conflict.") -> None:
        super().__init__(message)


class ForbiddenError(HRAgentError):
    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, message: str = "Access forbidden.") -> None:
        super().__init__(message)


class UnauthorizedError(HRAgentError):
    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, message: str = "Not authenticated.") -> None:
        super().__init__(message)
