from typing import Any, Optional, TypeVar, Generic

from pydantic import BaseModel, Field, ConfigDict
from fastapi import status
from fastapi.responses import JSONResponse

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """Standard API response model."""

    model_config = ConfigDict(populate_by_name=True)

    code: int = Field(description="Business status code")
    data: Optional[T] = Field(default=None, description="Response payload")
    message: str = Field(default="", description="Response message")


def create_response(
    http_code: int,
    code: Optional[int] = None,
    data: Any = None,
    message: str = "",
) -> JSONResponse:
    """
    Create a standardized JSON response.

    Args:
        http_code: HTTP status code
        code: Business status code (defaults to http_code if not provided)
        data: Response payload
        message: Response message
    """
    if code is None:
        code = http_code

    response = Response(code=code, data=data, message=message)
    return JSONResponse(
        status_code=http_code,
        content=response.model_dump(mode="json"),
    )


def response_ok(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Success",
) -> JSONResponse:
    """Create a successful response (200 OK)"""
    return create_response(status.HTTP_200_OK, code=code if code is not None else 0, data=data, message=message)


def response_created(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Created",
) -> JSONResponse:
    """Create a resource created response (201 Created)"""
    return create_response(status.HTTP_201_CREATED, code=code, data=data, message=message)


def response_bad_request(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Bad Request",
) -> JSONResponse:
    """Create a bad request error response (400 Bad Request)"""
    return create_response(status.HTTP_400_BAD_REQUEST, code=code, data=data, message=message)


def response_unauthorized(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Unauthorized",
) -> JSONResponse:
    """Create an unauthorized response (401 Unauthorized)"""
    return create_response(status.HTTP_401_UNAUTHORIZED, code=code, data=data, message=message)


def response_forbidden(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Forbidden",
) -> JSONResponse:
    """Create a forbidden response (403 Forbidden)"""
    return create_response(status.HTTP_403_FORBIDDEN, code=code, data=data, message=message)


def response_not_found(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Not Found",
) -> JSONResponse:
    """Create a not found response (404 Not Found)"""
    return create_response(status.HTTP_404_NOT_FOUND, code=code, data=data, message=message)


def response_conflict(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Conflict",
) -> JSONResponse:
    """Create a conflict response (409 Conflict)"""
    return create_response(status.HTTP_409_CONFLICT, code=code, data=data, message=message)


def response_unprocessable_entity(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Unprocessable Entity",
) -> JSONResponse:
    """Create an unprocessable entity response (422 Unprocessable Entity)"""
    return create_response(status.HTTP_422_UNPROCESSABLE_ENTITY, code=code, data=data, message=message)


def response_server_error(
    code: Optional[int] = None,
    data: Any = None,
    message: str = "Internal Server Error",
) -> JSONResponse:
    """Create a server error response (500 Internal Server Error)"""
    return create_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code=code, data=data, message=message)
