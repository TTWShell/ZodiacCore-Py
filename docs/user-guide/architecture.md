# Architecture Guide

This guide explains the **Layered Architecture** with **Dependency Injection** that ZodiacCore promotes for building maintainable, testable, and scalable FastAPI applications.

ZodiacCore recommends a **3-tier architecture** as the standard approach, but you can adapt it to your project's needs. This guide focuses on the 3-tier structure while also mentioning how to extend it to a 4-tier architecture when needed.

## Why This Architecture?

The layered architecture with DI provides:

- ✅ **Separation of Concerns**: Each layer has a clear responsibility
- ✅ **Testability**: Easy to mock dependencies and test in isolation
- ✅ **Maintainability**: Changes in one layer don't cascade to others
- ✅ **Scalability**: Easy to swap implementations (e.g., different databases)
- ✅ **Team Collaboration**: Clear boundaries for parallel development

## Architecture Layers

ZodiacCore supports flexible layered architectures. The standard template uses a **3-tier architecture**, but you can extend it to a **4-tier architecture** when your application requires additional separation of concerns.

### Standard 3-Tier Architecture

The recommended structure consists of three layers:

### 1. API (Presentation Layer)

**Location**: `app/api/`

**Responsibilities**:

- Handle HTTP requests and responses
- Validate input data (Pydantic schemas)
- Transform domain models to response schemas
- Route requests to appropriate services

**What it contains**:

- **Routers** (`app/api/routers/`): FastAPI route handlers
- **Schemas** (`app/api/schemas/`): Request/response Pydantic models

**Example**:
```python
from typing import Annotated
from dependency_injector.wiring import Provide, inject
from fastapi import Depends
from zodiac_core.pagination import PagedResponse, PageParams
from zodiac_core.routing import APIRouter

from app.api.schemas.item_schema import ItemSchema
from app.application.services.item_service import ItemService
from app.core.container import Container

router = APIRouter()

@router.get("", response_model=PagedResponse[ItemSchema])
@inject
async def list_items(
    page_params: Annotated[PageParams, Depends()],
    service: Annotated[ItemService, Depends(Provide[Container.item_service])],
):
    """List items with pagination."""
    return await service.list_items(page_params)
```

**Key Points**:

- Routers are **thin** - they delegate to services
- Dependencies are injected via `dependency-injector`
- Response models are defined here (API contract)

---

### 2. Application (Business Logic Layer)

**Location**: `app/application/`

**Responsibilities**:

- Implement business logic and use cases
- Orchestrate operations across multiple repositories
- Validate business rules
- Handle domain-level exceptions

**What it contains**:

- **Services** (`app/application/services/`): Business logic classes

**Example**:
```python
from loguru import logger
from zodiac_core.exceptions import NotFoundException
from zodiac_core.pagination import PagedResponse, PageParams

from app.infrastructure.database.models.item_model import ItemModel
from app.infrastructure.database.repositories.item_repository import ItemRepository

class ItemService:
    def __init__(self, item_repo: ItemRepository) -> None:
        self.item_repo = item_repo

    async def get_by_id(self, item_id: int) -> ItemModel:
        """Get an item by ID, raising NotFoundException if not found."""
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise NotFoundException(message=f"Item id '{item_id}' not found")
        return item

    async def list_items(self, page_params: PageParams) -> PagedResponse[ItemModel]:
        """List items with pagination."""
        result = await self.item_repo.list_items(page_params)
        logger.bind(
            page=page_params.page,
            size=page_params.size,
            total=result.total
        ).debug("list_items")
        return result
```

**Key Points**:

- Services contain **business logic**, not data access
- Services depend on repositories (infrastructure), not the other way around
- Business exceptions are raised here

---

### 3. Infrastructure (Implementation Layer)

**Location**: `app/infrastructure/`

**Responsibilities**:

- Implement data persistence (database, external APIs)
- Provide concrete implementations of abstractions
- Handle technical concerns (SQL queries, HTTP clients)

**What it contains**:

- **Database** (`app/infrastructure/database/`):
  - **Models** (`models/`): SQLModel table definitions
  - **Repositories** (`repositories/`): Data access classes
- **External** (`app/infrastructure/external/`): Third-party API clients

**Example - Repository**:
```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.pagination import PagedResponse, PageParams

from app.infrastructure.database.models.item_model import ItemModel

class ItemRepository(BaseSQLRepository):
    async def get_by_id(self, item_id: int) -> ItemModel | None:
        """Get an item by ID."""
        async with self.session() as session:
            stmt = select(ItemModel).where(ItemModel.id == item_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
        """List items with pagination using BaseSQLRepository.paginate_query."""
        stmt = select(ItemModel).order_by(ItemModel.id)
        return await self.paginate_query(stmt, params)
```

**Example - External Client**:
```python
from loguru import logger
from zodiac_core.http import ZodiacClient

class GitHubClient:
    def __init__(self, client: ZodiacClient) -> None:
        self.client = client

    async def fetch_homepage(self) -> str:
        """Fetch GitHub homepage HTML."""
        response = await self.client.get("https://github.com")
        logger.info("Fetched GitHub homepage")
        return response.text
```

**Key Points**:

- Repositories inherit from `BaseSQLRepository` for pagination and session management
- External clients use `ZodiacClient` for HTTP requests with trace ID injection
- Infrastructure is **swappable** - you can change databases or APIs without touching business logic

---

## Extended 4-Tier Architecture (Future)

When your application grows in complexity, you may want to introduce a **Domain Layer** between the Application and Infrastructure layers. This creates a 4-tier architecture with stricter separation of concerns:

### API Layer (4-Tier)
- Same as in 3-tier architecture
- Handles HTTP requests and responses
- Validates input data
- Transforms domain entities to response schemas

### Application Layer (4-Tier)

- **Location**: `app/application/`
- **Responsibilities**:
    - Orchestrates domain services and entities
    - Coordinates workflows and use cases
    - Handles application-level concerns (transactions, coordination)
    - Transforms between domain entities and infrastructure models
- **What it contains**:
    - **Services** (`app/application/services/`): Use case orchestration classes
    - **DTOs** (`app/application/dtos/`): Data transfer objects for application boundaries
- **Key Difference**: In 4-tier, Application layer focuses on orchestration rather than business logic

### Domain Layer - *Future Addition*

- **Location**: `app/domain/`
- **Responsibilities**:
    - Contains core business logic and domain models
    - Defines domain entities and value objects
    - Implements domain services
    - Enforces business rules and invariants
    - Defines repository interfaces (abstractions)
- **What it contains**:
    - **Entities** (`app/domain/entities/`): Domain models with business logic
    - **Value Objects** (`app/domain/value_objects/`): Immutable domain concepts
    - **Domain Services** (`app/domain/services/`): Domain-specific operations
    - **Repository Interfaces** (`app/domain/repositories/`): Abstract repository contracts

### Infrastructure Layer (4-Tier)

- Same structure as in 3-tier architecture
- **Key Difference**: Implements domain repository interfaces defined in the Domain layer
- Provides concrete implementations of domain abstractions

**Note**: The 4-tier architecture is not yet implemented in the standard template, but the structure is designed to accommodate this extension when needed. You can add the Domain layer as your application evolves.

---

## Dependency Injection Container

**Location**: `app/core/container.py`

The DI container wires all layers together, managing the lifecycle and dependencies of components.

### Container Definition

The container is typically defined in `app/core/container.py`: it declares providers (Factory/Singleton) for repositories, services, and other infrastructure. Only the **API layer** (routers) needs to request dependencies via `Depends(Provide[Container.xxx])`; the container injects service → repository and other lower-layer dependencies when it constructs those objects.

```python
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    item_repository = providers.Factory(ItemRepository)
    item_service = providers.Factory(ItemService, item_repo=item_repository)
    # ...
```

### Wiring

With **dependency-injector**, only the modules that **use** `Depends(Provide[Container.xxx])` must be "wired" to the container — i.e. the API router modules. You call `container.wire(modules=[...])` at startup with the list of those module names (e.g. `"app.api.routers.item_router"`). That way, when a route runs and asks for `Container.item_service`, the container can resolve it.

Service and infrastructure layers do **not** need to be wired: they are created by the container via `providers.Factory(...)` and receive their dependencies in the constructor.

### Benefits

- **Loose Coupling**: Components don't create their dependencies
- **Easy Testing**: Mock dependencies in tests
- **Configuration**: Centralized dependency configuration
- **Lifecycle Management**: Singleton vs Factory patterns

---

## Data Flow

### 3-Tier Architecture Flow

Here's how a request flows through the 3-tier layers:

```
HTTP Request
    ↓
[API Layer] Router receives request
    ↓ (injects service)
[Application Layer] Service implements business logic
    ↓ (uses repository)
[Infrastructure Layer] Repository queries database
    ↓ (returns data)
[Application Layer] Service processes and returns
    ↓ (transforms to schema)
[API Layer] Router returns response
    ↓
HTTP Response
```

### 4-Tier Architecture Flow (Future)

In a 4-tier architecture, the flow includes the Domain layer:

```
HTTP Request
    ↓
[API Layer] Router receives request
    ↓ (injects application service)
[Application Layer] Orchestrates use case
    ↓ (uses domain service/entity)
[Domain Layer] Business logic and rules
    ↓ (uses repository interface)
[Infrastructure Layer] Implements repository, queries database
    ↓ (returns domain entity)
[Domain Layer] Processes domain logic
    ↓ (returns domain entity)
[Application Layer] Transforms to DTO
    ↓ (transforms to schema)
[API Layer] Router returns response
    ↓
HTTP Response
```

### Example Flow: `GET /api/v1/items?page=1&size=20` (3-Tier)

1. **Router** (`item_router.py`):
   - Receives request with `PageParams`
   - Injects `ItemService` from container
   - Calls `service.list_items(page_params)`

2. **Service** (`item_service.py`):
   - Receives `PageParams`
   - Calls `item_repo.list_items(page_params)`
   - Logs the operation
   - Returns `PagedResponse[ItemModel]`

3. **Repository** (`item_repository.py`):
   - Builds SQL query: `select(ItemModel).order_by(ItemModel.id)`
   - Calls `paginate_query(stmt, params)`
   - Returns `PagedResponse[ItemModel]`

4. **Router** (back):
   - Transforms `ItemModel` to `ItemSchema` (via response_model)
   - Returns wrapped response

---

## Configuration

**Location**: `config/`

Configuration is managed through `.ini` files:

- `config/app.ini` - Base configuration (all environments)
- `config/app.develop.ini` - Development overrides
- `config/app.production.ini` - Production overrides

The container loads configuration:

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

Access configuration in the container:

```python
# In main.py lifespan
db_url = container.config.db.url()
db_echo = container.config.db.echo.as_(bool)
```

---

## Best Practices

### 1. Keep Layers Independent

- ✅ API layer doesn't import from Infrastructure (in 3-tier)
- ✅ Application layer doesn't know about FastAPI
- ✅ Infrastructure layer doesn't contain business logic
- ✅ Domain layer (4-tier) doesn't depend on Infrastructure or Application layers

### 2. Use Dependency Injection

- ✅ Inject dependencies via constructor
- ✅ Use the container to wire dependencies
- ❌ Don't create dependencies inside classes

### 3. Repository Pattern

- ✅ Use `BaseSQLRepository` for database operations
- ✅ Use `paginate_query()` for pagination
- ✅ Keep repositories focused on data access

### 4. Service Layer

- ✅ In 3-tier: Put business logic in application services
- ✅ In 4-tier: Put business logic in domain services/entities; application services orchestrate
- ✅ Services orchestrate repositories
- ✅ Raise domain exceptions (e.g., `NotFoundException`)

### 5. Response Schemas

- ✅ Define schemas in API layer
- ✅ Transform domain models to schemas
- ✅ Use Pydantic for validation

---

## Summary

The layered architecture with DI provides:

- **Clear separation** between presentation, business logic, and data access
- **Testability** through dependency injection
- **Maintainability** through well-defined boundaries
- **Scalability** through swappable implementations
- **Flexibility** to adapt to your project's needs (3-tier or 4-tier)

### Choosing Your Architecture

- **Start with 3-tier**: The standard template uses a 3-tier architecture, which is sufficient for most applications
- **Extend to 4-tier**: When you need stricter domain modeling and want to separate domain logic from application orchestration, you can introduce a Domain layer
- **Not mandatory**: ZodiacCore doesn't enforce a specific number of layers - choose what fits your project best

This architecture is the foundation of the `standard-3tier` template generated by `zodiac new`. Start with the template and extend it as your application grows.
