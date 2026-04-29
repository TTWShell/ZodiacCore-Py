from typing import Any, Optional

from fastapi import status


class ZodiacException(Exception):
    """Base class for all zodiac-core related errors."""

    http_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        code: Optional[int] = None,
        data: Any = None,
        message: Optional[str] = None,
    ):
        self.code = code or self.http_code
        self.data = data
        if message is not None:
            self.message = message
        super().__init__(message)


class BadRequestException(ZodiacException):
    """Exception raised for 400 Bad Request errors."""

    http_code = status.HTTP_400_BAD_REQUEST


class UpstreamServiceException(BadRequestException):
    """Exception raised when an upstream service is unavailable or fails unexpectedly."""

    def __init__(
        self,
        *,
        service: str,
        error_code: str = "UPSTREAM_SERVICE_ERROR",
        message: str = "Upstream service unavailable",
        upstream_status: Optional[int] = None,
    ):
        self.service = service
        self.error_code = error_code
        self.upstream_status = upstream_status
        super().__init__(
            message=message,
            data={
                "service": service,
                "error_code": error_code,
            },
        )


class UpstreamRequestException(UpstreamServiceException):
    """Exception raised when an upstream service rejects this service's request."""

    def __init__(
        self,
        *,
        service: str,
        upstream_status: Optional[int] = None,
    ):
        super().__init__(
            service=service,
            error_code="UPSTREAM_REQUEST_ERROR",
            message="Upstream request failed",
            upstream_status=upstream_status,
        )


class UnauthorizedException(ZodiacException):
    """Exception raised for 401 Unauthorized errors."""

    http_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenException(ZodiacException):
    """Exception raised for 403 Forbidden errors."""

    http_code = status.HTTP_403_FORBIDDEN


class NotFoundException(ZodiacException):
    """Exception raised for 404 Not Found errors."""

    http_code = status.HTTP_404_NOT_FOUND


class ConflictException(ZodiacException):
    """Exception raised for 409 Conflict errors."""

    http_code = status.HTTP_409_CONFLICT


class UnprocessableEntityException(ZodiacException):
    """Exception raised for 422 Unprocessable Entity (business validation / semantic errors)."""

    http_code = status.HTTP_422_UNPROCESSABLE_CONTENT
