# Standard Pagination

ZodiacCore provides a comprehensive pagination system that standardizes how your API handles list-based data. It includes request parameters, response models, and **professional repository methods** that automate pagination logic.

## 1. Request Parameters

The `PageParams` model handles typical pagination query strings (`?page=1&size=20`).

```python
from typing import Annotated
from fastapi import Depends
from zodiac_core.pagination import PageParams

@router.get("/items")
async def list_items(
    params: Annotated[PageParams, Depends()]
):
    # Automatically validated:
    # params.page defaults to 1 (min 1)
    # params.size defaults to 20 (max 100)
    ...
```

!!! tip "Using Depends() vs Query()"
    For Pydantic models like `PageParams`, use `Depends()` instead of `Query()`. FastAPI will automatically extract query parameters and validate them against the model.

---

## 2. Standard Paged Response

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

## 3. Professional Pagination with BaseSQLRepository

For database queries, `BaseSQLRepository` provides two methods that automate pagination:

### `paginate_query()` - Recommended for Most Cases

This is the **convenience method** that automatically manages the database session. Use this in your repository methods:

```python
from sqlalchemy import select
from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.pagination import PagedResponse, PageParams

class ItemRepository(BaseSQLRepository):
    async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
        """List items with pagination."""
        stmt = select(ItemModel).order_by(ItemModel.id)
        return await self.paginate_query(stmt, params)
```

**What it does:**

- ✅ Automatically manages database session
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

## 4. Complete Example

Here's a complete example showing the full flow:

**Repository:**
```python
class ItemRepository(BaseSQLRepository):
    async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
        stmt = select(ItemModel).order_by(ItemModel.id)
        return await self.paginate_query(stmt, params)
```

**Service:**
```python
class ItemService:
    def __init__(self, item_repo: ItemRepository) -> None:
        self.item_repo = item_repo

    async def list_items(self, page_params: PageParams) -> PagedResponse[ItemModel]:
        return await self.item_repo.list_items(page_params)
```

**Router:**
```python
@router.get("", response_model=PagedResponse[ItemSchema])
@inject
async def list_items(
    page_params: Annotated[PageParams, Depends()],
    service: Annotated[ItemService, Depends(Provide[Container.item_service])],
):
    return await service.list_items(page_params)
```

**No manual calculations needed!** The `paginate_query` method handles everything.

---

## 5. API Reference

### Pagination Models
::: zodiac_core.pagination
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PageParams
        - PagedResponse

### Repository Methods
::: zodiac_core.db.repository.BaseSQLRepository
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - paginate
        - paginate_query
