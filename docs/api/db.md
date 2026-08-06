# Database Engine & ORM

ZodiacCore provides a high-performance, async-first database abstraction layer built on top of **SQLModel** and **SQLAlchemy 2.0**. It simplifies session management, connection pooling, and standardizes model definitions.

## 1. Core Concepts

### The Database Manager
The `DatabaseManager` (exposed as the global `db` instance) is a strict singleton that manages the SQLAlchemy `AsyncEngine` and `async_sessionmaker`. It ensures that your process can reuse connection pools for the same named database instead of letting each app/container create its own pool, which is critical for performance and resource management.

### The Repository Pattern
We encourage the use of the **Repository Pattern** via `BaseSQLRepository`. This decouples your business logic from database-specific code, making your application more maintainable and easier to unit test with mocks.

---

## 2. Model Definitions

ZodiacCore provides several mixins and base classes in `zodiac_core.db.sql` to standardize your database schema.

### Standard Base Models
Instead of inheriting from `SQLModel` directly, we recommend using our pre-configured base models:

| Base Model | Primary Key | Timestamps |
| :--- | :--- | :--- |
| `IntIDModel` | `id: int` (Auto-increment) | `created_at`, `updated_at` |
| `UUIDModel` | `id: UUID` (v4) | `created_at`, `updated_at` |

### Example: Using Base Models
```python
from zodiac_core.db.sql import IntIDModel
from sqlmodel import Field

class User(IntIDModel, table=True):
    username: str = Field(unique=True, index=True)
    email: str
```

### Automatic Timestamps
Both `IntIDModel` and `UUIDModel` include `SQLDateTimeMixin`, which provides:

- **created_at**: Automatically set on insertion.
- **updated_at**: Automatically updated on every save via a SQLAlchemy event listener.

---

## 3. Configuration & Lifecycle

You should initialize the database during your application's startup and ensure it shuts down cleanly.
Calling `db.setup(...)` again with the same `name` is allowed only when the effective configuration is identical; different settings for an existing name raise `RuntimeError`.

> For multi‑app deployments with `app.mount()`, see the [Sub Applications](../user-guide/sub-applications.md) guide.
Lifecycle control is now **name-aware**:

- `await db.shutdown(name="...")` disposes only the selected named database.
- `await db.shutdown()` disposes all registered databases.

This lets multiple apps, containers, or resources share the global manager while still releasing only the resource they own.

### FastAPI Integration
We recommend using the **lifespan** context manager (FastAPI 0.93+). The legacy `on_event("startup")` / `on_event("shutdown")` are deprecated.

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from zodiac_core.db import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.setup(
        "postgresql+asyncpg://user:pass@localhost/dbname",
        pool_size=20,
        max_overflow=10,
        echo=False,
    )
    await db.create_all()  # Optional: create tables if they don't exist
    yield
    await db.shutdown()


app = FastAPI(lifespan=lifespan)
```

For a single-app service, `await db.shutdown()` is still the simplest shutdown path.
If you register multiple named databases or share the global `db` across multiple app lifecycles, prefer `await db.shutdown(name="...")` for scoped cleanup.

---

## 4. Choosing a Session API

The session APIs are intentionally not interchangeable. Choose the API from
the call site that owns the session lifecycle:

| Call site | Use |
| :--- | :--- |
| FastAPI endpoint owns a unit of work on the default database | `Depends(get_session)` |
| FastAPI endpoint owns a unit of work on a named database | A module-level dependency created by `session_dependency(name)` |
| Lower layer participates in an endpoint-owned unit of work | Accept the concrete `AsyncSession` from its caller |
| Service, repository, job, CLI, or startup task owns the unit of work | `BaseSQLRepository.session()` or `async with db.session(name)` |

!!! warning "FastAPI dependencies are not general session APIs"
    `get_session` retains its optional `name` argument for compatibility with
    ZodiacCore 0.7.0. When FastAPI resolves `Depends(get_session)`, however,
    the name comes from private server-side wiring and always selects the
    default database; it is never read from the request.

    For new named routes, call `session_dependency(name)` once at module or
    router scope and pass the stored callable to `Depends`. Existing
    server-side wrapper dependencies that iterate `get_session(name)` remain
    source-compatible. Migrate them when touched so FastAPI can propagate
    endpoint exceptions directly through rollback and cleanup. All
    `partial(get_session, ...)` forms are unsupported; replace them with
    `session_dependency(name)`. In particular, a keyword-bound partial is
    rejected while the route is registered instead of silently selecting the
    wrong database. Never pass `session_dependency` itself to `Depends`;
    FastAPI would treat its `name` as a required request parameter and, if
    supplied, inject a callable instead of an `AsyncSession`.

    A database name is trusted application wiring. Never derive it from a
    query parameter, path parameter, header, request body, or other request
    data.

    FastAPI dependencies are needed only when the endpoint deliberately owns
    the unit of work or performs database work directly. If it owns the unit of
    work, pass the concrete injected session to participating lower layers. If
    a service or repository owns the unit of work, it should use
    `db.session(name)` or `BaseSQLRepository.session()` instead.

### Default Database in FastAPI

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from zodiac_core.db import get_session


@app.get("/users")
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    ...
```

### Named Database in FastAPI

Create the dependency while defining the router. This only binds a trusted
name; it does not create a session or acquire a connection. The engine may be
registered later during application lifespan. Store and reuse the returned
callable: FastAPI's dependency cache and `app.dependency_overrides` identify it
by callable identity. By default, repeated uses of that stored callable within
one request share one session; a later request receives a new session. Passing
`DEFAULT_DB_NAME` returns `get_session`; ordinary default-database routes should
use `get_session` directly.

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from zodiac_core.db import session_dependency


get_analytics_session = session_dependency("analytics")


@app.get("/reports")
async def list_reports(
    session: Annotated[AsyncSession, Depends(get_analytics_session)],
):
    ...
```

### Compatibility with `get_session(name)`

The named-call API published in ZodiacCore 0.7.0 remains source- and
call-compatible, including existing zero-argument wrapper dependencies:

```python
async def legacy_analytics_session():
    async for session in get_session("analytics"):
        yield session
```

The name in this example is fixed by server code and cannot be replaced by a
request parameter. Preserve the wrapper when compatibility requires it, but
migrate touched routes and write new routes with
`session_dependency("analytics")`; the returned dependency lets FastAPI
propagate endpoint exceptions directly through session rollback and cleanup.
Do not replace the wrapper with `partial(get_session, ...)`; every partial form
is unsupported. A keyword-bound partial is rejected during route registration
because FastAPI dependency resolution would otherwise override its database
name. Use `session_dependency("analytics")` instead.

For code outside FastAPI that owns a unit of work, use the context manager
directly:

```python
from zodiac_core.db import db


async def rebuild_reports() -> None:
    async with db.session("analytics") as session:
        ...
        await session.commit()
```

Do not add a route session dependency merely because the route eventually
calls a repository. A `BaseSQLRepository` already owns its sessions by default;
use a route dependency only when the route intentionally owns a shared unit of
work or performs database work directly.

`db.setup()` creates one long-lived engine, connection pool, and
`async_sessionmaker` for each named database. An `AsyncSession` is not kept in
the connection pool: every dependency execution or `db.session(...)` context
creates a new session. It normally borrows a connection lazily and returns it
when the session closes. Never share an `AsyncSession` across requests or
concurrent tasks.

---

## 5. Working with Repositories

Inherit from `BaseSQLRepository` to create your data access layer.

```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository

from .models import User


class UserRepository(BaseSQLRepository):
    async def find_by_username(self, username: str) -> User | None:
        async with self.session() as session:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        async with self.session() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
```

---

## 6. Multi-Database Support

ZodiacCore supports multiple database connections simultaneously. This is essential for architectures involving:

- **Read-Write Splitting**: Routing writes to a Master and reads to a Replica.
- **Vertical Partitioning**: Storing different modules (e.g., Users, Analytics) in separate databases.

### Registering Named Databases
You can call `db.setup()` multiple times with different `name` arguments.

```python
# Primary Database (Master)
db.setup("postgresql+asyncpg://master_db_url", name="default")

# Read-only Replica
db.setup("postgresql+asyncpg://replica_db_url", name="read_only")
```

### Releasing Named Databases
Named shutdown is the companion to named setup:

```python
from zodiac_core.db import db


async def shutdown_named_databases() -> None:
    # Dispose only the replica pool
    await db.shutdown(name="read_only")

    # Dispose everything registered in the manager
    await db.shutdown()
```

Use named shutdown when the process keeps other databases alive, such as multi-app hosting, plugin-based services, or multiple DI resources sharing the same global manager.

### Binding Repositories to a Database
When creating a repository, specify which database it should use via `db_name`.

```python
from zodiac_core.db.repository import BaseSQLRepository


class ReadOnlyUserRepository(BaseSQLRepository):
    def __init__(self) -> None:
        # This repo will always use the 'read_only' engine
        super().__init__(db_name="read_only")

    async def get_total_users(self) -> int:
        async with self.session() as session:
            # Executes on replica
            ...
```

---

## 7. API Reference

### Session & Lifecycle
::: zodiac_core.db.session
    options:
      heading_level: 4
      show_root_heading: true
      members:
        - DatabaseManager
        - DEFAULT_DB_NAME
        - db
        - get_session
        - session_dependency
        - init_db_resource

### Repository Base
::: zodiac_core.db.repository.BaseSQLRepository
    options:
      heading_level: 4
      show_root_heading: true

### SQL Models & Mixins
::: zodiac_core.db.sql
    options:
      heading_level: 4
      show_root_heading: true
      members:
        - IntIDModel
        - UUIDModel
        - SQLDateTimeMixin
