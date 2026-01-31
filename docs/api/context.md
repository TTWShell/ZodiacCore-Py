# Tracing & HTTP Clients

ZodiacCore provides built-in support for **Distributed Tracing**. It ensures that a single Request ID (Trace ID) flows through your entire ecosystem: from the incoming request, through your logs, and out to downstream microservices via HTTP clients.

## 1. How it Works

1. **Extraction**: `TraceIDMiddleware` catches `X-Request-ID` from incoming headers (or generates a new one).
2. **Storage**: The ID is stored in a thread-safe `ContextVar` (managed by `zodiac_core.context`).
3. **Observation**: Logging utilities automatically pick up this ID from the context.
4. **Propagation**: `ZodiacClient` automatically injects this ID into outgoing HTTP requests.

---

## 2. Distributed Tracing (HTTP Clients)

When calling other services, use `ZodiacClient` (Async) or `ZodiacSyncClient` (Sync). They are thin wrappers around `httpx` that automatically handle Trace ID propagation.

### Async Usage (Recommended)
```python
from zodiac_core.http import ZodiacClient

async def call_downstream():
    async with ZodiacClient(base_url="https://api.internal.service") as client:
        # X-Request-ID is automatically added to headers
        response = await client.get("/data")
        return response.json()
```

### Sync Usage
```python
from zodiac_core.http import ZodiacSyncClient

def sync_call():
    with ZodiacSyncClient() as client:
        resp = client.get("https://google.com")
        return resp.status_code
```

---

## 3. Manual Context Access

In rare cases where you aren't using `ZodiacClient` (e.g., using `aiohttp` or `requests`), you can manually retrieve the current Request ID.

```python
from zodiac_core.context import get_request_id

request_id = get_request_id()
# Manually pass it to other systems...
```

---

## 4. API Reference

### HTTP Clients (Tracing Enabled)
::: zodiac_core.http
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - ZodiacClient
        - ZodiacSyncClient

### Context Utilities
::: zodiac_core.context
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - get_request_id
