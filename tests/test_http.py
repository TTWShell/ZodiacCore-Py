import uuid

import pytest
import respx
from httpx import Response

from zodiac_core.context import set_request_id
from zodiac_core.http import ZodiacClient, ZodiacSyncClient


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
