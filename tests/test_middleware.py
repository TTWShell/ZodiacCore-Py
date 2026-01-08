import json
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from zodiac_core import TraceIDMiddleware, get_request_id, setup_loguru
from zodiac_core.middleware import register_middleware


@pytest.mark.asyncio
async def test_trace_id_middleware():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    # Endpoint that returns the captured ID from context
    @app.get("/test")
    async def test_endpoint():
        return {"context_id": get_request_id()}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Test automatic generation
        resp = await client.get("/test")
        assert resp.status_code == 200
        data = resp.json()

        # Check Header
        header_id = resp.headers.get("X-Request-ID")
        assert header_id is not None
        # Check Context
        assert data["context_id"] == header_id

        # 2. Test passing existing ID
        custom_id = str(uuid.uuid4())
        resp = await client.get("/test", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200

        # Should persist
        assert resp.headers["X-Request-ID"] == custom_id
        assert resp.json()["context_id"] == custom_id


@pytest.mark.asyncio
async def test_context_reset():
    """Ensure context is cleared after request"""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/")
    async def root():
        return "ok"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/")

    # Context should be empty outside request
    assert get_request_id() is None


@pytest.mark.asyncio
class TestMiddlewareStack:

    @pytest.fixture
    def app(self):
        """Create a reusable FastAPI app with middleware stack registered."""
        app = FastAPI()
        register_middleware(app)

        @app.get("/log-test")
        async def log_endpoint():
            return {"msg": "ok"}

        return app

    async def test_stack_json_logging(self, app, capsys):
        """Test the middleware stack with JSON logging format."""
        setup_loguru(level="INFO", json_format=True, service_name="test-service")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/log-test")
            trace_id = resp.headers["X-Request-ID"]

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err.strip().split('\n')[-1])

        assert log_entry["record"]["extra"]["service"] == "test-service"
        assert log_entry["record"]["extra"]["request_id"] == trace_id
        assert log_entry["record"]["extra"]["path"] == "/log-test"
        assert "latency" in log_entry["record"]["extra"]

    async def test_stack_text_logging(self, app, capsys):
        """Test the middleware stack with Text logging format."""
        setup_loguru(level="INFO", json_format=False)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/log-test")
            trace_id = resp.headers["X-Request-ID"]

        captured = capsys.readouterr()
        last_log = captured.err.strip().split('\n')[-1]

        assert len(trace_id) == 36
        assert "GET /log-test" in last_log
        assert "200" in last_log
