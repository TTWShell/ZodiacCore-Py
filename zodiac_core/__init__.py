import importlib.metadata

from .config import ConfigManagement, Environment, StrictConfig
from .context import get_request_id, get_service_name, service_name_scope
from .exception_handlers import register_exception_handlers
from .exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
    ZodiacException,
)
from .http import ZodiacClient, ZodiacSyncClient, init_http_client
from .logging import LogFileOptions, setup_loguru
from .middleware import AccessLogMiddleware, ServiceNameMiddleware, TraceIDMiddleware, register_middleware
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
from .utils import strtobool

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
    "ServiceNameMiddleware",
    "AccessLogMiddleware",
    # http client
    "ZodiacClient",
    "ZodiacSyncClient",
    "init_http_client",
    # pagination
    "PageParams",
    "PagedResponse",
    # exceptions
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "UnprocessableEntityException",
    "ZodiacException",
    "register_exception_handlers",
    # logging
    "setup_loguru",
    "LogFileOptions",
    # context
    "get_request_id",
    "get_service_name",
    "service_name_scope",
    # config
    "ConfigManagement",
    "Environment",
    "StrictConfig",
    # utils
    "strtobool",
    # schemas
    "CoreModel",
    "IntIDSchema",
    "UUIDSchema",
    "IntIDSchemaMixin",
    "UUIDSchemaMixin",
    "DateTimeSchemaMixin",
    "UtcDatetime",
]
