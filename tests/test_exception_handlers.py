import json

import pytest
from fastapi.exceptions import RequestValidationError

from zodiac_core.exception_handlers import (
    handler_global_exception,
    handler_upstream_service_error,
    handler_validation_exception,
    handler_zodiac_exception,
)
from zodiac_core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
    UpstreamRequestError,
    ZodiacException,
)


class TestExceptionHandlers:
    media_type = "application/json"

    @pytest.mark.asyncio
    async def test_global_exception(self, mock_request):
        """Test handler_global_exception catches unknown exceptions as 500"""
        resp = await handler_global_exception(mock_request, Exception("unknown exception"))
        assert resp.status_code == 500
        assert resp.media_type == self.media_type

        data = json.loads(resp.body)
        assert data["code"] == 500
        assert data["message"] == "Internal Server Error"
        assert data["data"] is None

    def build_request_validation_error(self):
        from pydantic import BaseModel, Field, ValidationError

        class User(BaseModel):
            username: str = Field(min_length=3)
            age: int

        try:
            User(username="ab", age="not_int")
        except ValidationError as e:
            return RequestValidationError(e.errors())

    @pytest.mark.asyncio
    async def test_fastapi_request_validation_error(self, mock_request):
        """Test handler_validation_exception handles FastAPI validation errors"""
        exc = self.build_request_validation_error()
        resp = await handler_validation_exception(mock_request, exc)
        assert resp.status_code == 422
        assert resp.media_type == self.media_type

        data = json.loads(resp.body)
        assert data["code"] == 422
        assert data["message"] == "Unprocessable Entity"
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2

    def build_pydantic_validation_error(self):
        from pydantic import BaseModel, Field, ValidationError

        class User(BaseModel):
            username: str = Field(min_length=3)
            age: int

        try:
            User(username="ab", age="not_int")
        except ValidationError as e:
            return e

    @pytest.mark.asyncio
    async def test_pydantic_validation_error(self, mock_request):
        """Test handler_validation_exception handles raw Pydantic errors"""
        exc = self.build_pydantic_validation_error()
        resp = await handler_validation_exception(mock_request, exc)
        assert resp.status_code == 422

        data = json.loads(resp.body)
        assert data["code"] == 422
        assert isinstance(data["data"], list)

    @pytest.mark.parametrize(
        "exception_cls, init_kwargs, expected_status, expected_msg, expected_data",
        [
            (BadRequestException, {}, 400, "Bad Request", None),
            (BadRequestException, {"message": "Invalid ID"}, 400, "Invalid ID", None),
            (BadRequestException, {"data": {"id": 123}}, 400, "Bad Request", {"id": 123}),
            (UnauthorizedException, {}, 401, "Unauthorized", None),
            (ForbiddenException, {}, 403, "Forbidden", None),
            (NotFoundException, {}, 404, "Not Found", None),
            (ConflictException, {}, 409, "Conflict", None),
            (UnprocessableEntityException, {}, 422, "Unprocessable Entity", None),
            (ZodiacException, {}, 500, "Internal Server Error", None),
            # Custom business code test
            (BadRequestException, {"code": 1001, "message": "Custom Error"}, 400, "Custom Error", None),
        ],
    )
    @pytest.mark.asyncio
    async def test_zodiac_exception_handler(
        self,
        mock_request,
        exception_cls,
        init_kwargs,
        expected_status,
        expected_msg,
        expected_data,
    ):
        """Test handler_zodiac_exception with various exception types and parameters"""
        exc = exception_cls(**init_kwargs)
        resp = await handler_zodiac_exception(mock_request, exc)

        assert resp.status_code == expected_status
        data = json.loads(resp.body)
        # Verify custom code is preserved, fallback to status_code if not provided
        expected_code = init_kwargs.get("code", expected_status)
        assert data["code"] == expected_code
        assert data["message"] == expected_msg
        assert data["data"] == expected_data

    @pytest.mark.asyncio
    async def test_custom_subclass_exception(self, mock_request):
        """Test a realistic custom subclass as shown in documentation"""

        class InsufficientBalanceException(BadRequestException):
            def __init__(self, current_balance: float):
                super().__init__(
                    code=1001,
                    message="Your account balance is too low.",
                    data={"current_balance": current_balance},
                )

        exc = InsufficientBalanceException(current_balance=50.5)
        resp = await handler_zodiac_exception(mock_request, exc)

        assert resp.status_code == 400
        data = json.loads(resp.body)
        assert data["code"] == 1001
        assert data["message"] == "Your account balance is too low."
        assert data["data"] == {"current_balance": 50.5}

    @pytest.mark.asyncio
    async def test_upstream_service_error_handler(self, mock_request):
        """Upstream errors are handled by the standard upstream handler."""

        exc = UpstreamRequestError(service="production", upstream_status=422)
        resp = await handler_upstream_service_error(mock_request, exc)

        assert resp.status_code == 400
        data = json.loads(resp.body)
        assert data == {
            "code": 400,
            "message": "Upstream request failed",
            "data": {
                "service": "production",
                "error_code": "UPSTREAM_REQUEST_ERROR",
            },
        }

    @pytest.mark.asyncio
    async def test_register_exception_handlers_handles_upstream_errors(self):
        """Default exception registration handles translated upstream errors."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from zodiac_core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/upstream")
        def raise_upstream():
            raise UpstreamRequestError(service="production", upstream_status=422)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/upstream")

        assert resp.status_code == 400
        assert resp.json() == {
            "code": 400,
            "message": "Upstream request failed",
            "data": {
                "service": "production",
                "error_code": "UPSTREAM_REQUEST_ERROR",
            },
        }

    @pytest.mark.asyncio
    async def test_direct_zodiac_subclass_uses_declared_http_code(self, mock_request):
        """A direct ZodiacException subclass should use its declared HTTP status."""

        class InsufficientBalanceException(ZodiacException):
            http_code = 400

            def __init__(self, current_balance: float):
                super().__init__(
                    code=1001,
                    message="Your account balance is too low.",
                    data={"current_balance": current_balance},
                )

        exc = InsufficientBalanceException(current_balance=50.5)
        resp = await handler_zodiac_exception(mock_request, exc)

        assert resp.status_code == 400
        data = json.loads(resp.body)
        assert data["code"] == 1001
        assert data["message"] == "Your account balance is too low."
        assert data["data"] == {"current_balance": 50.5}

    @pytest.mark.asyncio
    async def test_builtin_exception_subclass_keeps_builtin_http_status(self, mock_request):
        """Subclasses of built-in exception families keep the family's HTTP status."""

        class MisclassifiedBadRequest(BadRequestException):
            http_code = 429

        exc = MisclassifiedBadRequest(
            code=2001,
            message="Still a bad request family error",
        )
        resp = await handler_zodiac_exception(mock_request, exc)

        assert resp.status_code == 400
        data = json.loads(resp.body)
        assert data["code"] == 2001
        assert data["message"] == "Still a bad request family error"
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_registered_handler_respects_direct_zodiac_subclass_http_code(self):
        """The registered FastAPI handler should preserve custom HTTP status codes."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from zodiac_core.exception_handlers import register_exception_handlers

        class RateLimitedException(ZodiacException):
            http_code = 429

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/limited")
        def limited():
            raise RateLimitedException(
                code=2001,
                message="Too many requests",
                data={"retry_after": 60},
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/limited")

        assert resp.status_code == 429
        assert resp.json() == {
            "code": 2001,
            "message": "Too many requests",
            "data": {"retry_after": 60},
        }

    @pytest.mark.asyncio
    async def test_register_exception_handlers(self):
        """Test that register_exception_handlers registers all handlers."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from zodiac_core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/err")
        def raise_err():
            raise ValueError("trigger global handler")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/err")
        assert resp.status_code == 500
        assert resp.json() == {
            "code": 500,
            "message": "Internal Server Error",
            "data": None,
        }
