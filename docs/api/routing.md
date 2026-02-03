# Routing & Response Wrapping

ZodiacCore enhances FastAPI's routing system to provide automatic response standardization. By using `APIRouter`, you ensure that every endpoint returns a consistent JSON structure without manual boilerplate.

## 1. The Zodiac APIRouter

The `APIRouter` in ZodiacCore is a drop-in replacement for `fastapi.APIRouter`. It uses a custom `ZodiacRoute` class that intercepts outgoing data and wraps it.

### Automatic Wrapping
When you return a dictionary, a Pydantic model, or a list from your route, Zodiac automatically wraps it in a `Response` model:

```python
from zodiac_core.routing import APIRouter

router = APIRouter()

@router.get("/status")
async def get_status():
    return {"status": "online"}
```

**Resulting JSON:**
```json
{
  "code": 0,
  "message": "Success",
  "data": {
    "status": "online"
  }
}
```

---

## 2. Standard Response Structure

All Zodiac responses follow this schema:

| Field | Type | Description |
| :--- | :--- | :--- |
| `code` | `int` | Business status code (0 for success). |
| `message` | `string` | A brief description of the result. |
| `data` | `any` | The actual payload (result of your function). |

### Manual Responses
If you need to return a non-standard response (e.g., a FileResponse or a custom status code), you can still return raw FastAPI `Response` objects or Zodiac's `Response` class. If the return type is already a `Response`, Zodiac will **not** wrap it again.

```python
from zodiac_core.response import response_ok

@router.get("/custom")
async def manual():
    return response_ok(message="Custom success", data={"id": 1})
```

---

## 3. OpenAPI Integration

ZodiacCore's `APIRouter` dynamically generates Pydantic models for your responses. This means your **Swagger UI** (`/docs`) will correctly display the wrapped structure, including the `code`, `message`, and `data` fields, mapped to your specific return type.

---

## 4. API Reference

### Routing Utilities
::: zodiac_core.routing
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - APIRouter
        - ZodiacRoute

### Response Helpers
::: zodiac_core.response
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - Response
        - create_response
        - response_ok
        - response_created
        - response_bad_request
        - response_unauthorized
        - response_forbidden
        - response_not_found
        - response_conflict
        - response_unprocessable_entity
        - response_server_error
