import importlib.metadata

from .config import ConfigManagement, Environment
from .context import get_request_id
from .db.repository import BaseSQLRepository
from .db.session import DEFAULT_DB_NAME
from .exception_handlers import register_exception_handlers
from .exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ZodiacException,
)
from .http import ZodiacClient, ZodiacSyncClient
from .logging import LogFileOptions, setup_loguru
from .middleware import AccessLogMiddleware, TraceIDMiddleware, register_middleware
from .pagination import PagedResponse, PageParams
from .response import (
    Response,
    create_response,
    response_bad_request,
    response_conflict,
    response_created,
    response_forbidden,
    response_not_found,
    response_ok,
    response_server_error,
    response_unauthorized,
    response_unprocessable_entity,
)
from .routing import APIRouter, ZodiacRoute
from .schemas import (
    CoreModel,
    DateTimeSchemaMixin,
    IntIDSchema,
    IntIDSchemaMixin,
    UtcDatetime,
    UUIDSchema,
    UUIDSchemaMixin,
)

try:
    __version__ = importlib.metadata.version("zodiac-core")
except importlib.metadata.PackageNotFoundError:
    # Package is not installed (e.g., during development without 'pip install -e .')
    __version__ = "unknown"

__all__ = [
    "__version__",
    # response
    "Response",
    "create_response",
    "response_ok",
    "response_created",
    "response_bad_request",
    "response_unauthorized",
    "response_forbidden",
    "response_not_found",
    "response_conflict",
    "response_unprocessable_entity",
    "response_server_error",
    # routing
    "ZodiacRoute",
    "APIRouter",
    # middleware
    "register_middleware",
    "TraceIDMiddleware",
    "AccessLogMiddleware",
    # http client
    "ZodiacClient",
    "ZodiacSyncClient",
    # pagination
    "PageParams",
    "PagedResponse",
    # db
    "BaseSQLRepository",
    "DEFAULT_DB_NAME",
    # exceptions
    "ZodiacException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "register_exception_handlers",
    # logging
    "setup_loguru",
    "LogFileOptions",
    # context
    "get_request_id",
    # config
    "ConfigManagement",
    "Environment",
    # schemas
    "CoreModel",
    "IntIDSchema",
    "UUIDSchema",
    "IntIDSchemaMixin",
    "UUIDSchemaMixin",
    "DateTimeSchemaMixin",
    "UtcDatetime",
]
