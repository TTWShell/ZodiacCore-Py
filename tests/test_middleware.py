import pytest
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from zodiac_core import TraceIDMiddleware, get_request_id


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
