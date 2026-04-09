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

## 4. Working with Repositories

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

## 5. Multi-Database Support

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

## 6. API Reference

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
