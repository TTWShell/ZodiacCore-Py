import json
import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from zodiac_core import ServiceNameMiddleware, TraceIDMiddleware, get_request_id, get_service_name, setup_loguru
from zodiac_core.middleware import AccessLogMiddleware, register_middleware


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
class TestTraceIDMiddleware:
    """TraceIDMiddleware: WebSocket and lifespan (non-HTTP) behavior."""

    async def test_websocket_sets_request_id_from_header(self):
        seen_request_id = []

        async def fake_app(scope, receive, send):
            seen_request_id.append(get_request_id())
            await send({"type": "websocket.accept"})

        middleware = TraceIDMiddleware(fake_app)
        custom_id = str(uuid.uuid4())
        scope = {
            "type": "websocket",
            "path": "/ws",
            "headers": [[b"x-request-id", custom_id.encode()]],
        }
        received = []

        async def fake_receive():
            return {"type": "websocket.disconnect"}

        async def fake_send(message):
            received.append(message)

        await middleware(scope, fake_receive, fake_send)
        assert len(received) == 1
        assert received[0]["type"] == "websocket.accept"
        assert seen_request_id == [custom_id]
        assert get_request_id() is None

    async def test_websocket_generates_request_id(self):
        seen_request_id = []

        async def fake_app(scope, receive, send):
            seen_request_id.append(get_request_id())
            await send({"type": "websocket.accept"})

        async def noop_send(m):
            pass

        middleware = TraceIDMiddleware(fake_app)
        scope = {"type": "websocket", "path": "/ws", "headers": []}
        await middleware(scope, lambda: {"type": "websocket.disconnect"}, noop_send)
        assert len(seen_request_id) == 1
        assert len(seen_request_id[0]) == 36
        assert get_request_id() is None

    async def test_lifespan_passthrough(self):
        seen_request_id = []

        async def fake_app(scope, receive, send):
            seen_request_id.append(get_request_id())
            await send({"type": "lifespan.startup.complete"})

        async def noop_send(m):
            pass

        middleware = TraceIDMiddleware(fake_app)
        scope = {"type": "lifespan"}
        await middleware(scope, lambda: {"type": "lifespan.startup"}, noop_send)
        assert seen_request_id == [None]


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

    async def test_stack_json_logging(self, app):
        """Test the middleware stack with JSON logging format."""
        # Use a list as a sink to capture logs reliably
        log_capture = []
        setup_loguru(
            level="INFO",
            json_format=True,
            service_name="test-service",
            # Force synchronous logging for tests
            console_options={"sink": log_capture.append, "enqueue": False},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/log-test")
            trace_id = resp.headers["X-Request-ID"]

        # Verify logs
        assert len(log_capture) > 0
        log_entry = json.loads(log_capture[-1])

        assert log_entry["record"]["extra"]["service"] == "test-service"
        assert log_entry["record"]["extra"]["request_id"] == trace_id
        assert log_entry["record"]["extra"]["path"] == "/log-test"
        assert "latency" in log_entry["record"]["extra"]

    async def test_stack_text_logging(self, app):
        """Test the middleware stack with Text logging format."""
        log_capture = []
        setup_loguru(
            level="INFO",
            json_format=False,
            # Force synchronous logging for tests
            console_options={"sink": log_capture.append, "enqueue": False},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/log-test")
            trace_id = resp.headers["X-Request-ID"]

        # Verify logs
        assert len(log_capture) > 0
        last_log = log_capture[-1]

        assert len(trace_id) == 36
        assert "GET /log-test" in last_log
        assert "200" in last_log

    async def test_stack_json_logging_uses_middleware_service_name(self):
        """Test service name can be scoped per app without reconfiguring loguru."""
        app = FastAPI()
        register_middleware(app, service_name="mounted-service")

        @app.get("/log-test")
        async def log_endpoint():
            return {"msg": "ok"}

        log_capture = []
        setup_loguru(
            level="INFO",
            json_format=True,
            service_name="default-service",
            console_options={"sink": log_capture.append, "enqueue": False},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/log-test")
            trace_id = resp.headers["X-Request-ID"]

        assert len(log_capture) > 0
        log_entry = json.loads(log_capture[-1])
        assert log_entry["record"]["extra"]["service"] == "mounted-service"
        assert log_entry["record"]["extra"]["request_id"] == trace_id
        assert get_service_name() is None


@pytest.mark.asyncio
class TestAccessLogMiddleware:
    """AccessLogMiddleware: WebSocket and lifespan behavior."""

    async def test_websocket_logs(self):
        last_log = []
        setup_loguru(
            level="INFO",
            json_format=False,
            console_options={"sink": last_log.append, "enqueue": False},
        )

        async def fake_app(scope, receive, send):
            await send({"type": "websocket.accept"})

        async def noop_send(m):
            pass

        middleware = AccessLogMiddleware(fake_app)
        scope = {"type": "websocket", "path": "/ws"}
        await middleware(scope, lambda: {"type": "websocket.disconnect"}, noop_send)
        assert len(last_log) >= 1
        log_line = last_log[-1]
        assert "WEBSOCKET" in log_line
        assert "/ws" in log_line
        assert "101" in log_line

    async def test_lifespan_passthrough(self):
        call_count = 0

        async def fake_app(scope, receive, send):
            nonlocal call_count
            call_count += 1

        async def noop_receive():
            return {}

        async def noop_send(msg):
            pass

        middleware = AccessLogMiddleware(fake_app)
        scope = {"type": "lifespan"}
        await middleware(scope, noop_receive, noop_send)
        assert call_count == 1


@pytest.mark.asyncio
class TestServiceNameMiddleware:
    async def test_http_sets_service_name(self):
        seen_service_name = []

        async def fake_app(scope, receive, send):
            seen_service_name.append(get_service_name())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def noop_receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def noop_send(_message):
            pass

        middleware = ServiceNameMiddleware(fake_app, service_name="mounted-service")
        await middleware({"type": "http", "path": "/", "headers": []}, noop_receive, noop_send)

        assert seen_service_name == ["mounted-service"]
        assert get_service_name() is None

    async def test_lifespan_passthrough(self):
        seen_service_name = []

        async def fake_app(scope, receive, send):
            seen_service_name.append(get_service_name())

        async def noop_receive():
            return {}

        async def noop_send(_message):
            pass

        middleware = ServiceNameMiddleware(fake_app, service_name="mounted-service")
        await middleware({"type": "lifespan"}, noop_receive, noop_send)

        assert seen_service_name == [None]
