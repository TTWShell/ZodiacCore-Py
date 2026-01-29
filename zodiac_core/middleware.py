import time
import uuid
from typing import Callable

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from zodiac_core.context import set_request_id, reset_request_id


def default_id_generator() -> str:
    return str(uuid.uuid4())


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Loguru-compatible Trace ID Middleware.

    1. Extracts/Generates X-Request-ID.
    2. Sets it in a ContextVar (via zodiac_core.context).
    3. Appends it to the Response headers.
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        generator: Callable[[], str] = None,
    ) -> None:
        super().__init__(app)
        self.header_name = header_name
        self.generator = generator or default_id_generator

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.header_name)
        if request_id is None or len(request_id) != 36:
            request_id = self.generator()

        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[self.header_name] = request_id
            return response
        finally:
            reset_request_id(token)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Standard Access Log Middleware.

    Logs request method, path, status code, and processing time (latency).
    Integrates with loguru (and will include request_id if TraceIDMiddleware is used).
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000

        logger.info(
            "{method} {path} - {status_code} - {latency:.2f}ms",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency=process_time,
        )

        return response


def register_middleware(app: ASGIApp):
    """
    Register standard Zodiac middleware stack.

    Ensures correct order:
    1. TraceIDMiddleware (Outer layer: generates ID)
    2. AccessLogMiddleware (Inner layer: logs with ID)
    """
    # Middleware is added in LIFO order (Last added is the Outer-most layer)

    # 2. Inner: Access Log
    app.add_middleware(AccessLogMiddleware)

    # 1. Outer: Trace ID
    app.add_middleware(TraceIDMiddleware)
