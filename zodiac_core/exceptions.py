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
