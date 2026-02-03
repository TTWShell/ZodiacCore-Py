# Basic Usage

This guide will walk you through building a complete, production-ready FastAPI application using `ZodiacCore` in 5 minutes.

## 1. Project Initialization

Create a file named `main.py`. This will be the entry point of your application.

First, we setup the core components: **Logging** and **Middleware**.

```python
from fastapi import FastAPI
from zodiac_core.routing import APIRouter
from zodiac_core.logging import setup_loguru
from zodiac_core.middleware import register_middleware
from zodiac_core.exception_handlers import register_exception_handlers

# 1. Initialize Logging (JSON format for production, trace_id injection)
setup_loguru(level="INFO", json_format=True, service_name="my-service")

app = FastAPI(title="Zodiac Demo App")
router = APIRouter()

# 2. Register Middleware (Trace ID, Access Logs)
register_middleware(app)

# 3. Register Global Exception Handlers (Standardized 4xx/5xx responses)
register_exception_handlers(app)

# 4. Include Router (Must be done after adding routes, but shown here for setup)
# app.include_router(router)
```

## 2. Standard Response Wrapper

When you use Zodiac's `APIRouter`, **all** successful responses are automatically wrapped in a standard structure. You don't need to manually return a `Response` object; just return your data (dict, Pydantic model, or list).

```python
@router.get("/profile")
async def get_profile():
    return {"username": "zodiac_user", "email": "user@example.com"}
```

The resulting JSON will be:
```json
{
  "code": 0,
  "message": "Success",
  "data": {
    "username": "zodiac_user",
    "email": "user@example.com"
  }
}
```

This ensures that your frontend developers always receive a predictable response format, whether it's a success or an error.

## 3. Handling Exceptions

Forget `try-except` blocks everywhere. Just raise `ZodiacException` subclasses.

```python
from zodiac_core.exceptions import NotFoundException, BadRequestException

@router.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id == 0:
        # Automatically returns 400 Bad Request with standard error format
        raise BadRequestException(message="Item ID cannot be zero")

    if item_id > 100:
        # Automatically returns 404 Not Found
        raise NotFoundException(message=f"Item {item_id} not found")

    return {"item_id": item_id}
```

!!! tip "Standard Error Format"
    The response will look like:
    ```json
    {
      "code": 404,
      "message": "Item 101 not found",
      "data": null
    }
    ```

## 4. Implementing Pagination

Use `PageParams` for input and `PagedResponse` for output. No more manual math.

```python
from typing import Annotated
from fastapi import Query
from pydantic import BaseModel
from zodiac_core.pagination import PageParams, PagedResponse

# Define a simple schema
class UserSchema(BaseModel):
    id: int
    name: str

# Mock database
USERS_DB = [UserSchema(id=i, name=f"User {i}") for i in range(1, 100)]

@router.get("/users", response_model=PagedResponse[UserSchema])
async def list_users(
    page_params: Annotated[PageParams, Query()]
):
    """
    Standard pagination endpoint.
    Query params: ?page=1&size=20
    """
    # Calculate offset
    skip = (page_params.page - 1) * page_params.size
    limit = page_params.size

    # Slice data (simulate DB query)
    data = USERS_DB[skip : skip + limit]
    total = len(USERS_DB)

    # Return standard paginated response
    return PagedResponse.create(
        items=data,
        total=total,
        params=page_params
    )
```

## 5. Database Integration (SQLModel)

Use `BaseSQLRepository` for a clean, async repository pattern with SQLModel.

First, define your model (using SQLModel or pure SQLAlchemy):

```python
from sqlmodel import Field
from zodiac_core.db.sql import IntIDModel

# Inherit from IntIDModel to get 'id', 'created_at', and 'updated_at' automatically
class Hero(IntIDModel, table=True):
    name: str
    secret_name: str
```

Then, create a repository:

```python
from typing import List, Optional
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository

class HeroRepository(BaseSQLRepository):

    async def create(self, hero: Hero) -> Hero:
        # Use self.session() context manager
        async with self.session() as session:
            session.add(hero)
            await session.commit()
            await session.refresh(hero)
            return hero

    async def get_all(self) -> List[Hero]:
        async with self.session() as session:
            stmt = select(Hero)
            result = await session.execute(stmt)
            return result.scalars().all()
```

Finally, use it in your route. Define a **lifespan** for DB lifecycle (FastAPI recommends this over the deprecated `on_event("startup")` / `on_event("shutdown")`). In **Step 1**, use `app = FastAPI(title="Zodiac Demo App", lifespan=lifespan)` instead of `app = FastAPI(...)`.

```python
from contextlib import asynccontextmanager
from zodiac_core.db.session import db

@asynccontextmanager
async def lifespan(app):
    db.setup("sqlite+aiosqlite:///database.db")
    await db.create_all()
    yield
    await db.shutdown()

# In Step 1, create app with: app = FastAPI(title="Zodiac Demo App", lifespan=lifespan)

@router.post("/heroes")
async def create_hero(hero: Hero):
    repo = HeroRepository()
    return await repo.create(hero)

# Finally, include the router in the app
app.include_router(router)
```

## Summary

You now have a fully functional application with:

- ✅ Structured Logging
- ✅ Trace ID Propagation
- ✅ Standard Error Handling
- ✅ Pagination Support
- ✅ Async Database Sessions

Run it with:
```bash
uvicorn main:app --reload
```