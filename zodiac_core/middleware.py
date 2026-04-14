"""
Middleware stack: Trace ID and Access Log.

Implemented as Pure ASGI middleware (no BaseHTTPMiddleware).

Scope types ("http", "websocket", "lifespan") follow the ASGI spec:
- https://asgi.readthedocs.io/en/stable/specs/www.html (http, websocket)
- https://asgi.readthedocs.io/en/stable/specs/lifespan.html (lifespan)
"""

import time
import uuid
from typing import Callable

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from zodiac_core.context import request_id_scope, service_name_scope


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
        # ASGI scope["type"]: "http" | "websocket" | "lifespan" (see module docstring links)
        if scope["type"] == "http":
            headers = MutableHeaders(scope=scope)
            header_value = headers.get(self.header_name)
            request_id = self.generator() if header_value is None or len(header_value) != 36 else header_value
            with request_id_scope(request_id):

                async def send_wrapper(message: Message) -> None:
                    if message["type"] == "http.response.start":
                        out_headers = MutableHeaders(scope=message)
                        out_headers.append(self.header_name, request_id)
                    await send(message)

                await self.app(scope, receive, send_wrapper)
            return
        if scope["type"] == "websocket":
            headers = MutableHeaders(scope=scope)
            header_value = headers.get(self.header_name)
            request_id = self.generator() if header_value is None or len(header_value) != 36 else header_value
            with request_id_scope(request_id):
                await self.app(scope, receive, send)
            return
        await self.app(scope, receive, send)


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
        # ASGI scope["type"]: "http" | "websocket" | "lifespan" (see module docstring links)
        if scope["type"] == "http":
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
                logger.info(
                    "{method} {path} - {status_code} - {latency:.2f}ms",
                    method=scope.get("method", "GET"),
                    path=scope.get("path", "/"),
                    status_code=status_code,
                    latency=process_time,
                )
            return
        if scope["type"] == "websocket":
            start_time = time.perf_counter()
            try:
                await self.app(scope, receive, send)
            finally:
                process_time = (time.perf_counter() - start_time) * 1000
                logger.info(
                    "WEBSOCKET {path} - 101 - {latency:.2f}ms",
                    path=scope.get("path", "/"),
                    latency=process_time,
                )
            return
        await self.app(scope, receive, send)


class ServiceNameMiddleware:
    """
    Service name middleware (Pure ASGI).

    Sets a per-request service name in context so mounted apps can keep
    app-local log attribution while sharing the process-wide logger sinks.
    """

    def __init__(self, app: ASGIApp, service_name: str) -> None:
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in {"http", "websocket"}:
            with service_name_scope(self.service_name):
                await self.app(scope, receive, send)
            return
        await self.app(scope, receive, send)


def register_middleware(app: ASGIApp, service_name: str | None = None) -> None:
    """
    Register TraceID and AccessLog middlewares in the correct order.

    Order: TraceID (outer) then ServiceName (optional) then AccessLog (inner),
    so the access log can include request_id and service from context.
    """
    app.add_middleware(AccessLogMiddleware)
    if service_name is not None:
        app.add_middleware(ServiceNameMiddleware, service_name=service_name)
    app.add_middleware(TraceIDMiddleware)
