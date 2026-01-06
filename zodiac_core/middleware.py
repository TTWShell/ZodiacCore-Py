import uuid
from typing import Callable

from fastapi import Request
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
        generator: Callable[[], str] = None
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
