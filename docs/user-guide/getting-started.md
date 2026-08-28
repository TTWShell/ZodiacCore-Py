# Getting Started

This guide will walk you through building a complete, production-ready FastAPI application using `ZodiacCore` in 5 minutes.

## 1. Generate Your Project

The easiest way to get started is using the **zodiac** CLI to scaffold a complete project structure. The CLI must be run from within a project directory (see [Installation](installation.md#about-uv)).

> **Note**: Replace `my_app` with your desired project name.

```bash
# Create a project directory and initialize with uv
mkdir my_app
cd my_app
uv init --python 3.12

# Install the CLI and SQL support (required by the standard-3tier template)
uv add "zodiac-core[zodiac,sql]"

# Generate the project (output to parent dir, allow generation into the existing directory with --force)
zodiac new my_app --tpl standard-3tier -o .. --force

# Add FastAPI CLI for running the app
uv add "fastapi[standard]" --dev

# Link packaged skills to this project's locked zodiac-core, then verify wiring
uv run zodiac skills install
uv run zodiac check

# Run the application
uv run fastapi run --reload
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
    config = providers.Configuration(strict=True)

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
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query
from zodiac_core.pagination import PageSortParams


@router.get("")
@inject
async def list_items(
    page_params: Annotated[PageSortParams, Query()],
    service: Annotated[ItemService, Depends(Provide[Container.item_service])],
):
    return await service.list_items(page_params)
```

### Professional Pagination with `paginate_query`

The generated project uses `BaseSQLRepository.paginate_query()` for pagination and sorting, which automatically handles:

- Session management
- Total count calculation
- Limit/offset application
- Sort whitelisting through `SortSpec`
- Response packaging

**Repository Example:**

```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.pagination import PagedResponse, PageSortParams, SortSpec


class ItemRepository(BaseSQLRepository):
    sort_spec = SortSpec(columns={"id": ItemModel.id, "name": ItemModel.name}, default=["id:asc"])

    async def list_items(self, params: PageSortParams) -> PagedResponse[ItemModel]:
        """List items with pagination and sorting using BaseSQLRepository.paginate_query."""
        stmt = select(ItemModel)
        return await self.paginate_query(stmt, params)
```

**Service Example:**

```python
from zodiac_core.pagination import PagedResponse, PageSortParams


class ItemService:
    def __init__(self, item_repo: ItemRepository) -> None:
        self.item_repo = item_repo

    async def list_items(self, page_params: PageSortParams) -> PagedResponse[ItemModel]:
        """List items with pagination."""
        return await self.item_repo.list_items(page_params)
```

**Router Example:**

```python
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query
from zodiac_core.pagination import PagedResponse, PageSortParams


@router.get("", response_model=PagedResponse[ItemSchema])
@inject
async def list_items(
    page_params: Annotated[PageSortParams, Query()],
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
- `config/app.testing.ini` - Test overrides for pytest and local integration runs
- `config/app.production.ini` - Production overrides you can add when needed

The generated template loads configuration from the `APPLICATION_ENVIRONMENT` environment variable and defaults to `develop` when it is unset:

```python
from pathlib import Path

from dependency_injector import containers, providers
from zodiac_core.config import ConfigManagement


class Container(containers.DeclarativeContainer):
    config = providers.Configuration(strict=True)


container = Container()
config_dir = Path(__file__).resolve().parent.parent / "config"
config_files = ConfigManagement.get_config_files(
    search_paths=[config_dir],
    env_var="APPLICATION_ENVIRONMENT",
    default_env="develop",
)
for path in config_files:
    container.config.from_ini(path, required=True)
```

Generated projects use `pytest-env` to set `APPLICATION_ENVIRONMENT=testing`
automatically. Their test configuration uses in-memory SQLite, so running pytest
does not create a local `data.db` file.

## 5. Standard Response Wrapper

When you use Zodiac's `APIRouter`, successful responses with a body are wrapped in a standard structure by default:

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

`response_model=None` keeps the standard envelope and uses an unconstrained `data` field. Return an actual FastAPI/Starlette response object to bypass wrapping. Status codes without a response body (`1xx`, `204`, `205`, and `304`) also bypass the envelope. See [Routing & Response Wrapping](../api/routing.md) for the complete behavior.

## 6. Handling Exceptions

Raise `ZodiacException` subclasses for automatic error handling:

```python
from zodiac_core.exceptions import BadRequestException, NotFoundException

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

The scaffolding flow in Step 1 already includes `uv run fastapi run --reload`. If you prefer `uvicorn` or need to re-sync dependencies:

```bash
uv sync
uv run uvicorn main:app --reload
```

Or use `uv run fastapi run --reload` (requires `fastapi[standard]`).

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
- ✅ **Agent-Ready Quality Loop** via `AGENTS.md`, `zodiac check`, and packaged developer skills

## Next Steps

- [Architecture Guide](architecture.md) — Layered design, DI container, and project structure
- [API Reference](../api/config.md) — Config, database, pagination, routing, schemas, and more
- [CLI Documentation](cli.md) — Scaffold new projects with `zodiac new` and verify wiring with `zodiac check`
- [Developer Skills](skills.md) — Install version-matched agent skills and run the quality loop
