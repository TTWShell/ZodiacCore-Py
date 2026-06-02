import json
import uuid

import httpx
import pytest
import respx
from httpx import Response
from loguru import logger

from zodiac_core.context import set_request_id
from zodiac_core.exceptions import UpstreamRequestException, UpstreamServiceException
from zodiac_core.http import (
    MAX_UPSTREAM_RESPONSE_LOG_CHARS,
    ZodiacClient,
    ZodiacSyncClient,
    init_http_client,
    translate_upstream_errors,
)


def _capture_warning_logs():
    logs = []
    sink_id = logger.add(logs.append, level="WARNING", serialize=True, enqueue=False)
    return logs, sink_id


class TestZodiacHttpClients:
    @pytest.fixture(autouse=True)
    def clear_context(self):
        """Ensure context is cleared before each test."""
        set_request_id(None)
        yield
        set_request_id(None)

    def test_sync_client_direct_usage(self):
        """Test using ZodiacSyncClient directly."""
        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)

        with respx.mock(base_url="http://test") as mock:
            mock.get("/foo").mock(return_value=Response(200))

            with ZodiacSyncClient(base_url="http://test") as client:
                client.get("/foo")

            assert mock.calls.call_count == 1
            assert mock.calls.last.request.headers["X-Request-ID"] == trace_id

    @pytest.mark.asyncio
    async def test_async_client_direct_usage(self):
        """Test using ZodiacClient directly."""
        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/foo").mock(return_value=Response(200))

            async with ZodiacClient(base_url="http://test") as client:
                await client.get("/foo")

            assert mock.calls.call_count == 1
            assert mock.calls.last.request.headers["X-Request-ID"] == trace_id

    def test_inheritance_usage(self):
        """Test that inheritance works as expected."""

        class MyService(ZodiacSyncClient):
            def get_data(self):
                return self.get("/data")

        trace_id = "test-trace-id"
        set_request_id(trace_id)

        with respx.mock(base_url="http://api") as mock:
            mock.get("/data").mock(return_value=Response(200, json={"status": "ok"}))

            with MyService(base_url="http://api") as client:
                resp = client.get_data()
                assert resp.json() == {"status": "ok"}

            assert mock.calls.last.request.headers["X-Request-ID"] == trace_id

    @pytest.mark.asyncio
    async def test_custom_hooks_preserved(self):
        """Test that custom hooks and trace injection work together."""

        async def custom_hook(request):
            request.headers["X-Custom"] = "val"

        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/").mock(return_value=Response(200))

            async with ZodiacClient(base_url="http://test", event_hooks={"request": [custom_hook]}) as client:
                await client.get("/")

            headers = mock.calls.last.request.headers
            assert headers["X-Request-ID"] == trace_id
            assert headers["X-Custom"] == "val"

    @pytest.mark.asyncio
    async def test_request_hook_as_single_callable(self):
        """Test that a single callable (non-list) for request hook is merged correctly with trace hook."""

        async def single_hook(request):
            request.headers["X-Single"] = "yes"

        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/").mock(return_value=Response(200))

            async with ZodiacClient(base_url="http://test", event_hooks={"request": single_hook}) as client:
                await client.get("/")

            headers = mock.calls.last.request.headers
            assert headers["X-Request-ID"] == trace_id
            assert headers["X-Single"] == "yes"

    @pytest.mark.asyncio
    async def test_init_http_client_resource_usage(self):
        """Test using init_http_client as a shared async client resource."""

        async def custom_hook(request):
            request.headers["X-Resource"] = "yes"

        trace_id = str(uuid.uuid4())
        set_request_id(trace_id)

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/resource").mock(return_value=Response(200))

            async with init_http_client(
                base_url="http://test",
                timeout=5.0,
                event_hooks={"request": [custom_hook]},
            ) as client:
                assert isinstance(client, ZodiacClient)
                await client.get("/resource")

            headers = mock.calls.last.request.headers
            assert headers["X-Request-ID"] == trace_id
            assert headers["X-Resource"] == "yes"

    @pytest.mark.asyncio
    async def test_translate_upstream_errors_maps_async_422_to_request_error(self):
        """HTTP 400/422 status errors are treated as upstream request failures."""

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/invalid").mock(return_value=Response(422, json={"code": 422}))

            async with ZodiacClient(base_url="http://test") as client:

                @translate_upstream_errors(service="identity_and_access")
                async def fetch_invalid():
                    response = await client.get("/invalid")
                    response.raise_for_status()

                with pytest.raises(UpstreamRequestException) as exc_info:
                    await fetch_invalid()

        exc = exc_info.value
        assert exc.service == "identity_and_access"
        assert exc.error_code == "UPSTREAM_REQUEST_ERROR"
        assert exc.upstream_status == 422
        assert exc.upstream_response_body == '{"code":422}'
        assert exc.upstream_response_body_truncated is False

    @pytest.mark.asyncio
    async def test_translate_upstream_errors_logs_http_context(self):
        """Translated HTTP status errors log enough context to diagnose the upstream failure."""
        logs, sink_id = _capture_warning_logs()

        try:
            async with respx.mock(base_url="http://test") as mock:
                mock.get("/invalid").mock(
                    return_value=Response(
                        422,
                        headers={"content-type": "application/json"},
                        json={"code": 422, "message": "missing required field"},
                    )
                )

                async with ZodiacClient(base_url="http://test") as client:

                    @translate_upstream_errors(service="identity_and_access")
                    async def fetch_invalid():
                        response = await client.get("/invalid")
                        response.raise_for_status()

                    with pytest.raises(UpstreamRequestException):
                        await fetch_invalid()
        finally:
            logger.remove(sink_id)

        record = json.loads(logs[-1])["record"]
        assert record["message"] == "Upstream HTTP error"
        assert record["extra"]["upstream_service"] == "identity_and_access"
        assert record["extra"]["upstream_error_type"] == "HTTPStatusError"
        assert record["extra"]["upstream_method"] == "GET"
        assert record["extra"]["upstream_url"] == "http://test/invalid"
        assert record["extra"]["upstream_status"] == 422
        assert record["extra"]["upstream_response_body"] == '{"code":422,"message":"missing required field"}'
        assert record["extra"]["upstream_response_body_truncated"] is False

    @pytest.mark.asyncio
    async def test_translate_upstream_errors_truncates_http_response_body_log(self):
        """Large upstream error responses are capped in logs."""
        logs, sink_id = _capture_warning_logs()
        response_body = "x" * (MAX_UPSTREAM_RESPONSE_LOG_CHARS + 1)

        try:
            async with respx.mock(base_url="http://test") as mock:
                mock.get("/large-error").mock(return_value=Response(503, text=response_body))

                async with ZodiacClient(base_url="http://test") as client:

                    @translate_upstream_errors(service="production")
                    async def fetch_large_error():
                        response = await client.get("/large-error")
                        response.raise_for_status()

                    with pytest.raises(UpstreamServiceException):
                        await fetch_large_error()
        finally:
            logger.remove(sink_id)

        record = json.loads(logs[-1])["record"]
        assert record["message"] == "Upstream HTTP error"
        assert record["extra"]["upstream_response_body"] == "x" * MAX_UPSTREAM_RESPONSE_LOG_CHARS
        assert record["extra"]["upstream_response_body_truncated"] is True

    def test_translate_upstream_errors_handles_unread_response_body_log(self):
        """Unread streaming responses should not break upstream error translation."""
        logs, sink_id = _capture_warning_logs()

        @translate_upstream_errors(service="production")
        def fetch_stream_error():
            request = httpx.Request("GET", "http://test/stream-error")
            response = httpx.Response(503, stream=httpx.ByteStream(b"unread"), request=request)
            raise httpx.HTTPStatusError("server error", request=request, response=response)

        try:
            with pytest.raises(UpstreamServiceException):
                fetch_stream_error()
        finally:
            logger.remove(sink_id)

        record = json.loads(logs[-1])["record"]
        assert record["message"] == "Upstream HTTP error"
        assert record["extra"]["upstream_response_body"] == "<response body not read>"
        assert record["extra"]["upstream_response_body_truncated"] is False

    @pytest.mark.asyncio
    async def test_translate_upstream_errors_maps_async_5xx_to_service_error(self):
        """Non-contract HTTP status errors are treated as upstream service failures."""

        async with respx.mock(base_url="http://test") as mock:
            mock.get("/unavailable").mock(return_value=Response(503, json={"code": 503}))

            async with ZodiacClient(base_url="http://test") as client:

                @translate_upstream_errors(service="production")
                async def fetch_unavailable():
                    response = await client.get("/unavailable")
                    response.raise_for_status()

                with pytest.raises(UpstreamServiceException) as exc_info:
                    await fetch_unavailable()

        exc = exc_info.value
        assert not isinstance(exc, UpstreamRequestException)
        assert exc.service == "production"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status == 503

    def test_translate_upstream_errors_maps_sync_transport_error(self):
        """Transport failures are treated as upstream service failures."""

        @translate_upstream_errors(service="deliverable_hub")
        def fetch_with_transport_failure():
            request = httpx.Request("GET", "http://deliverable-hub.test")
            raise httpx.ConnectError("connect failed", request=request)

        with pytest.raises(UpstreamServiceException) as exc_info:
            fetch_with_transport_failure()

        exc = exc_info.value
        assert exc.service == "deliverable_hub"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status is None

    def test_translate_upstream_errors_logs_request_error_context(self):
        """Transport/request failures log request metadata and the original httpx error text."""
        logs, sink_id = _capture_warning_logs()

        @translate_upstream_errors(service="deliverable_hub")
        def fetch_with_transport_failure():
            request = httpx.Request("GET", "http://deliverable-hub.test/items")
            raise httpx.ConnectError("connect failed", request=request)

        try:
            with pytest.raises(UpstreamServiceException):
                fetch_with_transport_failure()
        finally:
            logger.remove(sink_id)

        record = json.loads(logs[-1])["record"]
        assert record["message"] == "Upstream request error"
        assert record["extra"]["upstream_service"] == "deliverable_hub"
        assert record["extra"]["upstream_error_type"] == "ConnectError"
        assert record["extra"]["upstream_method"] == "GET"
        assert record["extra"]["upstream_url"] == "http://deliverable-hub.test/items"
        assert record["extra"]["upstream_error"] == "connect failed"

    def test_translate_upstream_errors_handles_request_error_without_request(self):
        """RequestError.request is optional, so logging should not require it."""
        logs, sink_id = _capture_warning_logs()

        @translate_upstream_errors(service="deliverable_hub")
        def fetch_with_requestless_failure():
            raise httpx.RequestError("request setup failed")

        try:
            with pytest.raises(UpstreamServiceException):
                fetch_with_requestless_failure()
        finally:
            logger.remove(sink_id)

        record = json.loads(logs[-1])["record"]
        assert record["message"] == "Upstream request error"
        assert record["extra"]["upstream_service"] == "deliverable_hub"
        assert record["extra"]["upstream_error_type"] == "RequestError"
        assert "upstream_method" not in record["extra"]
        assert "upstream_url" not in record["extra"]
        assert record["extra"]["upstream_error"] == "request setup failed"

    def test_translate_upstream_errors_maps_sync_request_error(self):
        """Non-transport request failures are also treated as upstream service failures."""

        @translate_upstream_errors(service="redirecting_service")
        def fetch_with_request_failure():
            request = httpx.Request("GET", "http://redirecting-service.test")
            raise httpx.TooManyRedirects("too many redirects", request=request)

        with pytest.raises(UpstreamServiceException) as exc_info:
            fetch_with_request_failure()

        exc = exc_info.value
        assert exc.service == "redirecting_service"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status is None

    def test_translate_upstream_errors_preserves_local_exception_handling(self):
        """If user code catches the httpx error itself, the decorator does not interfere."""

        @translate_upstream_errors(service="billing")
        def fetch_with_local_handling():
            request = httpx.Request("GET", "http://billing.test")
            try:
                raise httpx.ConnectError("connect failed", request=request)
            except httpx.ConnectError:
                return {"handled": True}

        assert fetch_with_local_handling() == {"handled": True}

    @pytest.mark.asyncio
    async def test_translated_upstream_error_is_handled_by_registered_fastapi_app(self):
        """Decorator + register_exception_handlers is the complete integration path."""
        from fastapi import FastAPI

        from zodiac_core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        @translate_upstream_errors(service="identity_and_access")
        async def call_upstream():
            async with ZodiacClient(base_url="http://upstream") as client:
                response = await client.get("/invalid")
                response.raise_for_status()

        @app.get("/proxy")
        async def proxy():
            await call_upstream()
            return {"ok": True}

        async with respx.mock(base_url="http://upstream") as mock:
            mock.get("/invalid").mock(return_value=Response(422, json={"code": 422}))
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/proxy")

        assert response.status_code == 400
        assert response.json() == {
            "code": 400,
            "message": "Upstream request failed",
            "data": {
                "service": "identity_and_access",
                "error_code": "UPSTREAM_REQUEST_ERROR",
                "upstream_status": 422,
                "upstream_response_body": '{"code":422}',
                "upstream_response_body_truncated": False,
            },
        }
