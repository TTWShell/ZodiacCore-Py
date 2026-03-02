"""
Middleware stack: Trace ID and Access Log.

Implemented as Pure ASGI middleware (no BaseHTTPMiddleware).
"""

import time
import uuid
from typing import Callable

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from zodiac_core.context import reset_request_id, set_request_id


def default_id_generator() -> str:
    return str(uuid.uuid4())


class TraceIDMiddleware:
    """
    Request ID middleware (Pure ASGI).

    1. Extracts or generates X-Request-ID.
    2. Sets it in a ContextVar (zodiac_core.context).
    3. Appends it to the response headers.

    Compatible with: app.add_middleware(TraceIDMiddleware) and
    app.add_middleware(TraceIDMiddleware, header_name="...", generator=...).
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        generator: Callable[[], str] | None = None,
    ) -> None:
        self.app = app
        self.header_name = header_name
        self.generator = generator or default_id_generator

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)
        header_value = headers.get(self.header_name)
        if header_value is None or len(header_value) != 36:
            request_id = self.generator()
        else:
            request_id = header_value

        token = set_request_id(request_id)
        try:

            async def send_wrapper(message: Message) -> None:
                if message["type"] == "http.response.start":
                    out_headers = MutableHeaders(scope=message)
                    out_headers.append(self.header_name, request_id)
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            reset_request_id(token)


class AccessLogMiddleware:
    """
    Access log middleware (Pure ASGI).

    Logs method, path, status code, and latency. Uses loguru; request_id
    appears in logs when TraceIDMiddleware is used (context).

    Compatible with: app.add_middleware(AccessLogMiddleware).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            process_time = (time.perf_counter() - start_time) * 1000
            method = scope.get("method", "GET")
            path = scope.get("path", "/")
            logger.info(
                "{method} {path} - {status_code} - {latency:.2f}ms",
                method=method,
                path=path,
                status_code=status_code,
                latency=process_time,
            )


def register_middleware(app: ASGIApp) -> None:
    """
    Register TraceID and AccessLog middlewares in the correct order.

    Order: TraceID (outer) then AccessLog (inner), so the access log
    can include the request_id from context.
    """
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TraceIDMiddleware)
