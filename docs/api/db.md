# Database Engine & ORM

ZodiacCore provides a high-performance, async-first database abstraction layer built on top of **SQLModel** and **SQLAlchemy 2.0**. It simplifies session management, connection pooling, and standardizes model definitions.

## 1. Core Concepts

### The Database Manager
The `DatabaseManager` (exposed as the global `db` instance) is a strict singleton that manages the SQLAlchemy `AsyncEngine` and `async_sessionmaker`. It ensures that your application maintains a single connection pool, which is critical for performance and resource management.

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

### FastAPI Integration
```python
from fastapi import FastAPI
from zodiac_core.db.session import db

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    # Configure pool size, max_overflow, etc.
    db.setup(
        "postgresql+asyncpg://user:pass@localhost/dbname",
        pool_size=20,
        max_overflow=10,
        echo=False
    )
    # Optional: Create tables if they don't exist
    await db.create_all()

@app.on_event("shutdown")
async def on_shutdown():
    await db.shutdown()
```

---

## 4. Working with Repositories

Inherit from `BaseSQLRepository` to create your data access layer.

```python
from zodiac_core.db.repository import BaseSQLRepository
from sqlalchemy import select
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

### Binding Repositories to a Database
When creating a repository, specify which database it should use via `db_name`.

```python
class ReadOnlyUserRepository(BaseSQLRepository):
    def __init__(self):
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
