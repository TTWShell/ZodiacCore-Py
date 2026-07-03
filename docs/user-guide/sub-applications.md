# Sub Applications (Mounts)

FastAPI supports mounting multiple independent applications under a single
parent process via [`app.mount()`][fastapi-mount].  Each sub-application has
its own routes and middleware stack, but all of them share the same Python
process — and therefore the same global resources (loguru logger, database
connection pools, cache backends).

[fastapi-mount]: https://fastapi.tiangolo.com/advanced/sub-applications/

## Middleware Ownership

`register_middleware()` installs `TraceIDMiddleware`, `ServiceNameMiddleware`,
and `AccessLogMiddleware` on the target app.  **Do not** register middleware on
both the parent and a sub-application for the same request path — a request
routed through a mount already passes through the sub-app's middleware stack.
Adding middleware on the parent as well causes duplicate request IDs and
double access-log entries.

**Recommended**: register middleware on each sub-application that owns
endpoints.

```python
from fastapi import FastAPI
from zodiac_core.logging import setup_loguru
from zodiac_core.middleware import register_middleware

setup_loguru(level="INFO", json_format=True, service_name="gateway")

parent_app = FastAPI()
orders_app = FastAPI()
users_app = FastAPI()

register_middleware(orders_app, service_name="orders")
register_middleware(users_app, service_name="users")

parent_app.mount("/orders", orders_app)
parent_app.mount("/users", users_app)
```

If the parent app has its own routes (e.g. `/health`), register middleware on
the parent **only for those routes** and be aware that requests to mounted
sub-apps will also pass through the parent's middleware — trace IDs and
access logs will appear twice unless you explicitly skip them (for example via
`exclude_paths`).

## Sub-application Lifespan

`app.mount()` does **not** trigger sub-application lifespan events.  If a
sub-app uses `lifespan` for resource setup (e.g. `db.setup()`), the parent
must enter its lifespan context explicitly:

```python
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI


orders_app = create_orders_app()
users_app = create_users_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            orders_app.router.lifespan_context(orders_app)
        )
        await stack.enter_async_context(
            users_app.router.lifespan_context(users_app)
        )
        yield


parent_app = FastAPI(lifespan=lifespan)
parent_app.mount("/orders", orders_app)
parent_app.mount("/users", users_app)
```

Without this, any `lifespan` logic on a sub-application is silently skipped.

## Logging: One Setup, Per-App Identity

`setup_loguru()` configures the process-wide logger.  Call it **once** in the
entry point.  Per-app identity comes from `register_middleware(app,
service_name=...)` — the patcher resolves the service name at log time:

1. **Request-scoped**: value from `ServiceNameMiddleware` (ContextVar)
2. **Global fallback**: `service_name` passed to `setup_loguru()`

## Database: Shared or Named

`db.setup()` supports named engines.  Use the default name for a shared
database, or distinct names when sub-apps need their own:

```python
from zodiac_core.db.session import db

# Shared — all apps use the same database
db.setup("postgresql+asyncpg://shared_db_url")

# Per-app — separate databases
db.setup("postgresql+asyncpg://orders_db_url", name="orders")
db.setup("postgresql+asyncpg://users_db_url", name="users")
```

Repositories bind to a named engine via `db_name`:

```python
class OrderRepository(BaseSQLRepository):
    def __init__(self):
        super().__init__(db_name="orders")
```

!!! info "Idempotent"
    Calling `db.setup()` again with the same `name` and identical configuration
    is harmless.  Different configuration for an existing name raises
    `RuntimeError`.

## Cache: Shared or Named

`cache.setup()` requires a `prefix` and supports optional `name` for isolation:

```python
from zodiac_core.cache.manager import cache

# Shared
cache.setup(prefix="shared")

# Per-app
cache.setup(prefix="orders", name="orders")
cache.setup(prefix="users", name="users")
```

Use `cache.get_cache(name)` to obtain a specific backend instance.

## Shutdown Ownership

The component that calls `setup` is responsible for calling `shutdown`.

!!! warning
    `db.shutdown()` and `cache.shutdown()` **without a `name` close every**
    **registered resource**, not just the default.  In a multi-app process,
    always pass an explicit `name` to shut down only the intended resource:

    ```python
    await db.shutdown(name="orders")       # close only "orders"
    await cache.shutdown(name="orders")    # close only "orders"
    ```

If the parent app entered sub-app lifespans, those lifespans should call
`db.shutdown(name="...")` and `cache.shutdown(name="...")` for the resources
they created, rather than relying on a bare `shutdown()`.

## Summary

| Concern | API | Call site |
|---------|-----|-----------|
| Log sinks & format | `setup_loguru()` | Once, entry point |
| Per-app log identity | `register_middleware(app, service_name=...)` | Each sub-app |
| Middleware (trace / access log) | `register_middleware(app)` | Each sub-app |
| Database (shared) | `db.setup(url)` | Entry point or lifespan |
| Database (per-app) | `db.setup(url, name="...")` | Sub-app lifespan or entry point |
| Cache (shared) | `cache.setup(prefix="...")` | Entry point or lifespan |
| Cache (per-app) | `cache.setup(prefix="...", name="...")` | Sub-app lifespan or entry point |
