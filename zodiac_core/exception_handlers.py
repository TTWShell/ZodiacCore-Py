from http import HTTPStatus
from typing import Union

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError
from starlette.requests import Request

from .exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
    UpstreamServiceError,
    ZodiacException,
)
from .response import (
    create_response,
    response_bad_request,
    response_conflict,
    response_forbidden,
    response_not_found,
    response_server_error,
    response_unauthorized,
    response_unprocessable_entity,
)


async def handler_zodiac_exception(
    request: Request,
    exc: ZodiacException,
) -> JSONResponse:
    """
    Handle generic business exceptions (ZodiacException and subclasses).
    Uses the code, message and data defined in the exception instance.
    """
    kwargs = dict(code=exc.code, data=exc.data)
    if hasattr(exc, "message"):
        kwargs["message"] = exc.message

    match exc:
        case BadRequestException():
            return response_bad_request(**kwargs)
        case UnauthorizedException():
            return response_unauthorized(**kwargs)
        case ForbiddenException():
            return response_forbidden(**kwargs)
        case NotFoundException():
            return response_not_found(**kwargs)
        case ConflictException():
            return response_conflict(**kwargs)
        case UnprocessableEntityException():
            return response_unprocessable_entity(**kwargs)
        case _:
            return create_response(
                http_code=exc.http_code,
                code=exc.code,
                data=exc.data,
                message=getattr(exc, "message", HTTPStatus(exc.http_code).phrase),
            )


async def handler_validation_exception(
    request: Request,
    exc: Union[RequestValidationError, ValidationError],
) -> JSONResponse:
    """Handle 422 Validation Errors"""
    return response_unprocessable_entity(data=exc.errors())


async def handler_global_exception(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 Global Uncaught Exceptions"""
    logger.error(f"Unhandled exception occurred accessing {request.url.path}: {exc}", exc_info=True)
    return response_server_error()


async def handler_upstream_service_error(
    request: Request,
    exc: UpstreamServiceError,
) -> JSONResponse:
    """
    Handle upstream service errors as explicit third-party call failures.

    The upstream-call decorators are the opt-in boundary. Once an upstream
    error is translated into this exception family, it participates in the
    standard application exception registration.
    """
    logger.warning(
        "Returning upstream error to client service={} error_code={} upstream_status={}",
        exc.service,
        exc.error_code,
        exc.upstream_status,
    )
    return response_bad_request(
        message=exc.message,
        data={
            "service": exc.service,
            "error_code": exc.error_code,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers to the FastAPI app.

    Order matters:
    1. Specific Validation Errors
    2. Specific Upstream Service Errors
    3. Custom Business Logic Errors (ZodiacException)
    4. Global Catch-All (Exception)
    """
    app.add_exception_handler(RequestValidationError, handler_validation_exception)
    app.add_exception_handler(ValidationError, handler_validation_exception)
    app.add_exception_handler(UpstreamServiceError, handler_upstream_service_error)
    app.add_exception_handler(ZodiacException, handler_zodiac_exception)
    app.add_exception_handler(Exception, handler_global_exception)
