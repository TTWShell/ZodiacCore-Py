import json

import pytest
from fastapi.exceptions import RequestValidationError

from zodiac_core.exception_handlers import (
    handler_global_exception,
    handler_validation_exception,
    handler_zodiac_exception,
)
from zodiac_core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
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
