import uuid

import httpx
import pytest
import respx
from httpx import Response

from zodiac_core.context import set_request_id
from zodiac_core.exceptions import UpstreamRequestError, UpstreamServiceError
from zodiac_core.http import (
    ZodiacClient,
    ZodiacSyncClient,
    init_http_client,
    translate_upstream_errors,
)


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

                with pytest.raises(UpstreamRequestError) as exc_info:
                    await fetch_invalid()

        exc = exc_info.value
        assert exc.service == "identity_and_access"
        assert exc.error_code == "UPSTREAM_REQUEST_ERROR"
        assert exc.upstream_status == 422

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

                with pytest.raises(UpstreamServiceError) as exc_info:
                    await fetch_unavailable()

        exc = exc_info.value
        assert not isinstance(exc, UpstreamRequestError)
        assert exc.service == "production"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status == 503

    def test_translate_upstream_errors_maps_sync_transport_error(self):
        """Transport failures are treated as upstream service failures."""

        @translate_upstream_errors(service="deliverable_hub")
        def fetch_with_transport_failure():
            request = httpx.Request("GET", "http://deliverable-hub.test")
            raise httpx.ConnectError("connect failed", request=request)

        with pytest.raises(UpstreamServiceError) as exc_info:
            fetch_with_transport_failure()

        exc = exc_info.value
        assert exc.service == "deliverable_hub"
        assert exc.error_code == "UPSTREAM_SERVICE_ERROR"
        assert exc.upstream_status is None

    def test_translate_upstream_errors_maps_sync_request_error(self):
        """Non-transport request failures are also treated as upstream service failures."""

        @translate_upstream_errors(service="redirecting_service")
        def fetch_with_request_failure():
            request = httpx.Request("GET", "http://redirecting-service.test")
            raise httpx.TooManyRedirects("too many redirects", request=request)

        with pytest.raises(UpstreamServiceError) as exc_info:
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
            },
        }
