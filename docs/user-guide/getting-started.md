# Getting Started

This guide will walk you through building a complete, production-ready FastAPI application using `ZodiacCore` in 5 minutes.

## 1. Generate Your Project

The easiest way to get started is using the **zodiac CLI** to scaffold a complete project structure:

```bash
# Install the CLI
uv add "zodiac-core[zodiac]"

# Generate a new project
zodiac new my_app --tpl standard-3tier -o ./projects
cd projects/my_app
```

The `standard-3tier` template generates a project following the **Standard 3-Tier Layered Architecture** with **Dependency Injection**:

- **API (Presentation)**: FastAPI routers and request/response handling
- **Application (Logic)**: Business logic and use case orchestration
- **Infrastructure (Implementation)**: Database models, repositories, and external integrations

The project uses `dependency-injector` for managing component dependencies, providing clean separation of concerns and making the codebase more testable and maintainable.

> **Note**: While the template uses a 3-tier architecture, ZodiacCore supports flexible layered architectures. You can extend it to a 4-tier architecture with a Domain layer when needed. See the [Architecture Guide](architecture.md) for details.

## 2. Project Structure

After generation, your project will have this structure:

```
my_app/
├── app/
│   ├── api/              # Presentation layer (routers, schemas)
│   │   ├── routers/
│   │   └── schemas/
│   ├── application/      # Business logic layer (services)
│   │   └── services/
│   ├── infrastructure/   # Implementation layer (DB, external clients)
│   │   ├── database/
│   │   └── external/
│   └── core/             # DI container and configuration
├── config/               # Environment-based configuration files
├── tests/                # Test suite
└── main.py               # Application entry point
```

## 3. Understanding the Architecture

### Dependency Injection Container

The project uses `dependency-injector` to manage dependencies. The container is defined in `app/core/container.py`.

```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Infrastructure layer
    item_repository = providers.Factory(ItemRepository)

    # Application layer
    item_service = providers.Factory(
        ItemService,
        item_repo=item_repository,
    )
```

Dependencies are injected into routers using FastAPI's `Depends`. In `main.py`, the generated project uses `Container.initialize([config_dir])`, which loads config from `.ini` and wires all router modules (files named `*_router.py`) under `app.api.routers`; when you add a new router file, it is picked up automatically.

```python
from dependency_injector.wiring import Provide, inject
from fastapi import Depends

@router.get("")
@inject
async def list_items(
    service: Annotated[ItemService, Depends(Provide[Container.item_service])],
):
    return await service.list_items(params)
```

### Professional Pagination with `paginate_query`

The generated project uses `BaseSQLRepository.paginate_query()` for pagination, which automatically handles:

- Session management
- Total count calculation
- Limit/offset application
- Response packaging

**Repository Example:**

```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.pagination import PagedResponse, PageParams

class ItemRepository(BaseSQLRepository):
    async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
        """List items with pagination using BaseSQLRepository.paginate_query."""
        stmt = select(ItemModel).order_by(ItemModel.id)
        return await self.paginate_query(stmt, params)
```

**Service Example:**

```python
class ItemService:
    def __init__(self, item_repo: ItemRepository) -> None:
        self.item_repo = item_repo

    async def list_items(self, page_params: PageParams) -> PagedResponse[ItemModel]:
        """List items with pagination."""
        return await self.item_repo.list_items(page_params)
```

**Router Example:**

```python
@router.get("", response_model=PagedResponse[ItemSchema])
@inject
async def list_items(
    page_params: Annotated[PageParams, Depends()],
    service: Annotated[ItemService, Depends(Provide[Container.item_service])],
):
    """List items with pagination."""
    return await service.list_items(page_params)
```

No manual `skip`/`limit` calculations needed! The `paginate_query` method handles everything automatically.

## 4. Configuration

The project uses file-based configuration. Configuration files are in the `config/` directory:

- `config/app.ini` - Base configuration
- `config/app.develop.ini` - Development overrides
- `config/app.production.ini` - Production overrides

The configuration is loaded based on the `ENV` environment variable:

```python
from pathlib import Path
from zodiac_core.config import ConfigManagement

config_dir = Path(__file__).resolve().parent.parent / "config"
config_files = ConfigManagement.get_config_files(
    search_paths=[config_dir],
    env_var="ENV",
    default_env="develop",
)
container.config.from_ini(*config_files)
```

## 5. Standard Response Wrapper

When you use Zodiac's `APIRouter`, **all** successful responses are automatically wrapped in a standard structure:

```python
@router.get("/items/{item_id}")
async def get_item(item_id: int):
    return {"id": 1, "name": "Example"}
```

The resulting JSON will be:
```json
{
  "code": 0,
  "message": "Success",
  "data": {
    "id": 1,
    "name": "Example"
  }
}
```

## 6. Handling Exceptions

Raise `ZodiacException` subclasses for automatic error handling:

```python
from zodiac_core.exceptions import NotFoundException, BadRequestException

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id == 0:
        raise BadRequestException(message="Item ID cannot be zero")

    item = await service.get_by_id(item_id)
    if not item:
        raise NotFoundException(message=f"Item {item_id} not found")

    return item
```

The response will automatically follow the standard error format:
```json
{
  "code": 404,
  "message": "Item 101 not found",
  "data": null
}
```

## 7. Running Your Application

Install dependencies and run:

```bash
# Install dependencies
uv sync

# Run the application
uv run uvicorn main:app --reload
```

Visit:

- API Documentation: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/api/v1/health

## Summary

You now have a fully functional application with:

- ✅ **3-Tier Layered Architecture** with Dependency Injection
- ✅ **Professional Pagination** using `paginate_query`
- ✅ **Structured Logging** with trace ID propagation
- ✅ **Standard Error Handling** with automatic response wrapping
- ✅ **File-based Configuration** for different environments
- ✅ **Async Database Sessions** with SQLModel

## Next Steps

- [Architecture Guide](architecture.md) — Layered design, DI container, and project structure
- [API Reference](../api/config.md) — Config, database, pagination, routing, schemas, and more
- [CLI Documentation](cli.md) — Scaffold new projects and modules with `zodiac new`
