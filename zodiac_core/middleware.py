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

from zodiac_core.context import request_id_scope


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
            await self._handle_http(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _get_or_generate_request_id(self, scope: Scope) -> str:
        headers = MutableHeaders(scope=scope)
        header_value = headers.get(self.header_name)
        if header_value is None or len(header_value) != 36:
            return self.generator()
        return header_value

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_id = self._get_or_generate_request_id(scope)
        with request_id_scope(request_id):

            async def send_wrapper(message: Message) -> None:
                if message["type"] == "http.response.start":
                    out_headers = MutableHeaders(scope=message)
                    out_headers.append(self.header_name, request_id)
                await send(message)

            await self.app(scope, receive, send_wrapper)

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_id = self._get_or_generate_request_id(scope)
        with request_id_scope(request_id):
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
            await self._handle_http(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _log_access(
        self,
        scope: Scope,
        start_time: float,
        method: str | None = None,
        status_code: int = 500,
    ) -> None:
        process_time = (time.perf_counter() - start_time) * 1000
        method = method or scope.get("method", "GET")
        path = scope.get("path", "/")
        logger.info(
            "{method} {path} - {status_code} - {latency:.2f}ms",
            method=method,
            path=path,
            status_code=status_code,
            latency=process_time,
        )

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        start_time = time.perf_counter()
        log_info: dict[str, int] = {"status_code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                log_info["status_code"] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self._log_access(scope, start_time, status_code=log_info["status_code"])

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        start_time = time.perf_counter()
        try:
            await self.app(scope, receive, send)
        finally:
            self._log_access(scope, start_time, method="WEBSOCKET", status_code=101)


def register_middleware(app: ASGIApp) -> None:
    """
    Register TraceID and AccessLog middlewares in the correct order.

    Order: TraceID (outer) then AccessLog (inner), so the access log
    can include the request_id from context.
    """
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(TraceIDMiddleware)
