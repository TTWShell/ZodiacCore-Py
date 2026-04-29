import pytest

from zodiac_core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
    UpstreamRequestException,
    UpstreamServiceException,
    ZodiacException,
)


@pytest.mark.parametrize(
    "exception_class, expected_http_code",
    [
        (ZodiacException, 500),
        (BadRequestException, 400),
        (UnauthorizedException, 401),
        (ForbiddenException, 403),
        (NotFoundException, 404),
        (ConflictException, 409),
        (UnprocessableEntityException, 422),
    ],
)
class TestZodiacExceptions:
    def test_default_values(self, exception_class, expected_http_code):
        exc = exception_class()
        assert exc.code == expected_http_code
        assert exc.data is None
        assert not hasattr(exc, "message") or exc.message is None

    def test_custom_message(self, exception_class, expected_http_code):
        msg = "Custom error message"
        exc = exception_class(message=msg)
        assert exc.message == msg
        assert exc.code == expected_http_code

    def test_custom_code(self, exception_class, expected_http_code):
        custom_code = 10001
        exc = exception_class(code=custom_code)
        assert exc.code == custom_code

    def test_with_data(self, exception_class, expected_http_code):
        data = {"field": "username", "reason": "taken"}
        exc = exception_class(data=data)
        assert exc.data == data
        assert exc.code == expected_http_code

    def test_all_params(self, exception_class, expected_http_code):
        msg = "All in one"
        code = 999
        data = [1, 2, 3]
        exc = exception_class(message=msg, code=code, data=data)
        assert exc.message == msg
        assert exc.code == code
        assert exc.data == data


class TestUpstreamExceptions:
    def test_upstream_service_error_defaults_to_bad_request_shape(self):
        exc = UpstreamServiceException(service="production", upstream_status=503)

        assert isinstance(exc, BadRequestException)
        assert isinstance(exc, ZodiacException)
        assert exc.code == 400
        assert exc.message == "Upstream service unavailable"
        assert exc.service == "production"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status == 503
        assert exc.data == {
            "service": "production",
            "error_code": "UPSTREAM_SERVICE_ERROR",
        }

    def test_upstream_request_error_uses_request_failure_code(self):
        exc = UpstreamRequestException(service="identity_and_access", upstream_status=422)

        assert isinstance(exc, UpstreamServiceException)
        assert isinstance(exc, BadRequestException)
        assert isinstance(exc, ZodiacException)
        assert exc.code == 400
        assert exc.message == "Upstream request failed"
        assert exc.service == "identity_and_access"
        assert exc.error_code == "UPSTREAM_REQUEST_ERROR"
        assert exc.upstream_status == 422
        assert exc.data == {
            "service": "identity_and_access",
            "error_code": "UPSTREAM_REQUEST_ERROR",
        }
