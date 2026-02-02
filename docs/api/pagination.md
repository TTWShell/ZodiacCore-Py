# Standard Pagination

ZodiacCore provides a set of Pydantic models to standardize how your API handles list-based data. It simplifies reading query parameters and ensures a consistent response structure for your frontend.

## 1. Request Parameters

The `PageParams` model handles typical pagination query strings (`?page=1&size=20`).

```python
from typing import Annotated
from fastapi import Query, Depends
from zodiac_core.pagination import PageParams

@app.get("/items")
async def list_items(
    params: Annotated[PageParams, Query()]
):
    # Automatically validated:
    # params.page defaults to 1 (min 1)
    # params.size defaults to 20 (max 100)

    offset = (params.page - 1) * params.size
    limit = params.size
    ...
```

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
from .schemas import UserSchema

@app.get("/users", response_model=PagedResponse[UserSchema])
async def get_users(params: Annotated[PageParams, Query()]):
    users, total_count = await db.find_users(params)

    return PagedResponse.create(
        items=users,
        total=total_count,
        params=params
    )
```

---

## 3. API Reference

### Pagination Models
::: zodiac_core.pagination
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PageParams
        - PagedResponse