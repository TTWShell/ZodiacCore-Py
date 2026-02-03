# Middleware Stack

ZodiacCore provides a standard stack of middlewares to handle cross-cutting concerns like request tracing, latency monitoring, and access logging.

## 1. Core Middlewares

### Trace ID Middleware
The `TraceIDMiddleware` is the entry point for observability. It:

1. **Reads**: Looks for an `X-Request-ID` header in the incoming request.
2. **Generates**: If missing, it generates a fresh UUID.
3. **Persists**: Sets the ID in the request context (via `zodiac_core.context`).
4. **Responds**: Attaches the same ID to the response headers for frontend tracking.

### Access Log Middleware
The `AccessLogMiddleware` records every HTTP transaction. It logs:

- HTTP Method and Path.
- Status Code.
- Processing Latency (in milliseconds).
- The associated Trace ID (automatically picked up from the context).

---

## 2. Usage & Order

The simplest way to use these is via `register_middleware`.

!!! info "Middleware Order"
    ZodiacCore adds middlewares in a specific order to ensure that the **Trace ID** is generated *before* the **Access Log** tries to record it.

```python
from fastapi import FastAPI
from zodiac_core.middleware import register_middleware

app = FastAPI()

# Registers both TraceID and AccessLog middlewares in the correct order
register_middleware(app)
```

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