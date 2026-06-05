# Middleware Stack

ZodiacCore provides a standard stack of **Pure ASGI** middlewares for request tracing, service log attribution, latency monitoring, and access logging. They handle HTTP and WebSocket; lifespan scope is passed through unchanged.

## 1. Core Middlewares

### Trace ID Middleware
The `TraceIDMiddleware` is the entry point for observability. It:

1. **Reads**: Looks for an `X-Request-ID` header in the incoming request (HTTP) or WebSocket upgrade request.
2. **Generates**: If missing or invalid (not 36 characters), it generates a fresh UUID.
3. **Persists**: Sets the ID in the request context (via `zodiac_core.context`) for the duration of the request or WebSocket connection, then resets it.
4. **Responds**: For HTTP, attaches the same ID to the response headers for frontend tracking.

### Service Name Middleware
The `ServiceNameMiddleware` stores the current service name in request context so logs can attribute entries to the correct app or mounted service. It is most useful when multiple apps share one process-wide logger sink, or when you want every request log to carry an explicit service label.

Use it through `register_middleware(service_name=...)` instead of adding it manually in normal applications.

### Access Log Middleware
The `AccessLogMiddleware` records HTTP requests and WebSocket connections. It logs:

- **HTTP**: Method, path, status code, and processing latency (ms). Trace ID is picked up from context when present.
- **WebSocket**: Path and latency with a fixed status `101` (Switching Protocols). Trace ID is available in context for the connection lifetime.
- **Lifespan**: Not logged; scope is passed through.

Use `exclude_paths` to skip noisy HTTP access logs such as health checks. Paths are matched exactly against `scope["path"]`, without query strings. For example, `"/api/v1/health"` matches only that path.

---

## 2. Usage & Order

The simplest way to use these is via `register_middleware`. Call it once per app and pass all options in the same call.

!!! info "Middleware Order"
    ZodiacCore adds middlewares in a specific order: Trace ID is set first, Service Name is scoped next when configured, and Access Log records after the downstream app finishes.

```python
from fastapi import FastAPI
from zodiac_core.middleware import register_middleware

app = FastAPI()

register_middleware(
    app,
    service_name="inventory-service",
    exclude_paths=[
        "/api/v1/health",
    ],
)
```

`exclude_paths` affects HTTP access logs only. WebSocket access logs are still recorded.

---

## 3. Customizing Trace ID Generation

If you want to use a custom header name or a different ID generator (e.g., K-Sorted IDs), you can add the middleware manually:

```python
from zodiac_core.middleware import TraceIDMiddleware

app.add_middleware(
    TraceIDMiddleware,
    header_name="X-Correlation-ID",
    generator=lambda: "my-custom-id-123"
)
```

---

## 4. API Reference

### Middleware Utilities
::: zodiac_core.middleware
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - register_middleware
        - TraceIDMiddleware
        - AccessLogMiddleware
        - ServiceNameMiddleware
