# Standard Pagination

ZodiacCore provides a comprehensive pagination system that standardizes how your API handles list-based data. It includes request parameters, response models, and **professional repository methods** that automate pagination logic.

## 1. Request Parameters

The `PageParams` model handles typical pagination query strings (`?page=1&size=20`).
Use `SortParams` or `PageSortParams` when an endpoint also supports repeated multi-column sort parameters such as `?sort=name:asc&sort=created_at:desc`.

```python
from typing import Annotated

from fastapi import Query
from zodiac_core.pagination import PageParams
from zodiac_core.routing import APIRouter

router = APIRouter()


@router.get("/items")
async def list_items(
    params: Annotated[PageParams, Query()],
):
    # Automatically validated:
    # params.page defaults to 1 (min 1)
    # params.size defaults to 20 (max 100)
    ...
```

!!! tip "Query Parameter Models"
    FastAPI officially documents Pydantic query parameter models with `Query()`. `PageParams` follows that pattern: FastAPI extracts `page` and `size` from the query string and validates them against the model.

---

## 2. Multi-Column Sorting

Use `PageSortParams` for paginated list APIs that support sorting:

```python
from typing import Annotated

from fastapi import Query
from zodiac_core.pagination import PageSortParams


@router.get("/items")
async def list_items(
    params: Annotated[PageSortParams, Query()],
):
    # /items?page=1&size=20&sort=name:asc&sort=created_at:desc
    # params.sort == ["name:asc", "created_at:desc"]
    ...
```

Use `SortParams` directly for endpoints that need sorting without pagination. Sort directions are limited to `asc` and `desc`; when omitted, the direction defaults to `asc`.

If you do not use ZodiacCore repository helpers, consume `params.sort_pairs` directly:

```python
for field, direction in params.sort_pairs:
    ...
```

For SQL repositories, define a reusable `SortSpec` once on the repository:

```python
from sqlalchemy import select
from zodiac_core.pagination import PageSortParams, SortSpec


class ItemRepository(BaseSQLRepository):
    sort_spec = SortSpec(
        columns={
            "name": ItemModel.name,
            "created_at": ItemModel.created_at,
        },
        default=["created_at:desc", "name:asc"],
    )

    async def list_items(self, params: PageSortParams):
        return await self.paginate_query(select(ItemModel), params)
```

The public query field is a list of strings, so OpenAPI documents `sort` as repeated string parameters:

```text
?sort=name:asc&sort=created_at:desc
```

`paginate_query()` parses those strings internally and applies the repository `SortSpec`. Unknown sort fields raise `BadRequestException`; this keeps public API field names explicit and avoids sorting by arbitrary database columns.

`sort_columns` remains supported for backward compatibility and one-off calls, but `SortSpec` is the preferred API for repository code:

```python
return await self.paginate_query(
    select(ItemModel),
    params,
    sort_columns={
        "name": ItemModel.name,
        "created_at": ItemModel.created_at,
    },
)
```

---

## 3. Standard Paged Response

The `PagedResponse[T]` is a generic model that wraps your data items along with metadata.

### The Response Structure
```json
{
  "code": 0,
  "message": "Success",
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "size": 20
  }
}
```

### Building the Response
Use the `.create()` factory method to easily build the response from your query results and the input `PageParams`.

```python
from zodiac_core.pagination import PagedResponse

return PagedResponse.create(
    items=items,
    total=total_count,
    params=page_params
)
```

---

## 4. Professional Pagination with BaseSQLRepository

For database queries, `BaseSQLRepository` provides methods that automate pagination and sorting:

### `paginate_query()` - Recommended for Most Cases

This is the **convenience method** that automatically manages the database session. Use this in your repository methods:

```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.pagination import PagedResponse, PageSortParams, SortSpec


class ItemRepository(BaseSQLRepository):
    sort_spec = SortSpec(
        columns={
            "id": ItemModel.id,
            "name": ItemModel.name,
            "created_at": ItemModel.created_at,
        },
        default=["id:asc"],
    )

    async def list_items(self, params: PageSortParams) -> PagedResponse[ItemModel]:
        """List items with pagination."""
        stmt = select(ItemModel)
        return await self.paginate_query(stmt, params)
```

**What it does:**

- ✅ Automatically manages database session
- ✅ Optionally applies multi-column sorting with repository-level `SortSpec` or per-call `sort_columns`
- ✅ Calculates total count (handles complex queries with joins/groups)
- ✅ Applies limit/offset
- ✅ Packages results into `PagedResponse`

**When to use:**
- Most repository methods that need pagination
- Simple queries that don't require custom session management

### `paginate()` - For Advanced Use Cases

This method requires you to manage the session yourself. Use this when you need more control:

```python
async def list_items_with_custom_logic(self, params: PageParams) -> PagedResponse[ItemModel]:
    """Example with custom session management."""
    async with self.session() as session:
        # You can add custom logic here (e.g., filtering, joins)
        stmt = select(ItemModel).where(ItemModel.status == "active")
        stmt = stmt.order_by(ItemModel.created_at.desc())

        return await self.paginate(session, stmt, params)
```

**What it does:**

- ✅ Calculates total count (handles complex queries)
- ✅ Applies limit/offset
- ✅ Packages results into `PagedResponse`
- ⚠️ Requires you to provide an active session

**When to use:**

- When you need custom session management
- When you want to perform multiple operations in a single transaction
- When you need to add complex query logic before pagination

### How Count Calculation Works

Both methods handle complex queries correctly:

- **Simple queries**: `SELECT COUNT(*) FROM (SELECT ...)`
- **Queries with joins**: Automatically wraps in subquery
- **Queries with GROUP BY**: Handles correctly
- **Queries with ORDER BY**: Removed from count query (as expected)

The implementation removes `limit`/`offset` before counting and safely wraps complex queries in subqueries.

### Transformation Support

Both methods support optional transformation to Pydantic models:

```python
from app.api.schemas.item_schema import ItemSchema

# Transform DB models to response schemas
return await self.paginate_query(stmt, params, transformer=ItemSchema)
```

---

## 5. Complete Example

Here's a complete example showing the full flow:

**Repository:**
```python
from zodiac_core.pagination import PagedResponse, PageSortParams, SortSpec


class ItemRepository(BaseSQLRepository):
    sort_spec = SortSpec(columns={"id": ItemModel.id, "name": ItemModel.name}, default=["id:asc"])

    async def list_items(self, params: PageSortParams) -> PagedResponse[ItemModel]:
        return await self.paginate_query(select(ItemModel), params)
```

**Service:**
```python
from zodiac_core.pagination import PagedResponse, PageSortParams


class ItemService:
    def __init__(self, item_repo: ItemRepository) -> None:
        self.item_repo = item_repo

    async def list_items(self, page_params: PageSortParams) -> PagedResponse[ItemModel]:
        return await self.item_repo.list_items(page_params)
```

**Router:**
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
    return await service.list_items(page_params)
```

**No manual calculations needed!** The `paginate_query` method handles everything.

---

## 6. API Reference

### Pagination Models
::: zodiac_core.pagination
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PageParams
        - SortParams
        - SortSpec
        - PageSortParams
        - PagedResponse

### Repository Methods
::: zodiac_core.db.repository.BaseSQLRepository
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - apply_sorting
        - paginate
        - paginate_query
