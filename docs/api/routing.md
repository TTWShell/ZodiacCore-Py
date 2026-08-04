# Routing & Response Wrapping

ZodiacCore enhances FastAPI's routing system with default response standardization. Body-bearing endpoints use a consistent JSON structure without manual boilerplate, while raw response objects and HTTP no-body response semantics remain available.

## 1. The Zodiac APIRouter

The `APIRouter` in ZodiacCore accepts FastAPI-style route declarations while adding a mandatory envelope for ordinary response data. It uses a custom `ZodiacRoute` class to wrap response models and returned values.

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

When `response_model` is omitted, Zodiac infers the payload type from the endpoint's return annotation. An endpoint without a return annotation uses `Response[Any]`.

### Response Model Semantics

| Route declaration | Runtime behavior | OpenAPI response model |
| :--- | :--- | :--- |
| Omitted `response_model`, return type `T` | Automatically wrapped | `Response[T]` |
| Omitted `response_model`, no return type | Automatically wrapped | `Response[Any]` |
| `response_model=T` | Automatically wrapped | `Response[T]` |
| `response_model=None`, ordinary return value | Automatically wrapped without constraining `data` | `Response[Any]` |
| `response_model` omitted or set to `None`, return type is a FastAPI/Starlette `Response` | Raw response is passed through | No Zodiac envelope model |
| Status code `<200`, `204`, `205`, or `304` | No response body or envelope | No response content |

Declaring a non-empty response model for a status code that prohibits a body remains an error, matching FastAPI.

Unlike FastAPI's native router, Zodiac intentionally treats `response_model=None` as an untyped payload rather than as an envelope opt-out. This preserves the `code`, `data`, and `message` contract. Runtime passthrough is based on the actual returned FastAPI/Starlette `Response` object; its return annotation keeps OpenAPI aligned with that raw response.

---

## 2. Standard Response Structure

Body-bearing responses wrapped by Zodiac follow this schema:

| Field | Type | Description |
| :--- | :--- | :--- |
| `code` | `int` | Business status code (0 for success). |
| `message` | `string` | A brief description of the result. |
| `data` | `any` | The actual payload (result of your function). |

### Manual Responses

Raw FastAPI/Starlette `Response` objects, such as `FileResponse` and `StreamingResponse`, are passed through without runtime wrapping. Annotate the raw response return type so OpenAPI does not advertise a Zodiac envelope.

```python
from fastapi import Response

@router.get("/custom")
async def manual() -> Response:
    return Response("custom", media_type="text/plain")
```

---

## 3. OpenAPI Integration

ZodiacCore's `APIRouter` dynamically generates Pydantic models for wrapped responses. Swagger UI (`/docs`) displays the `code`, `message`, and `data` fields, with `data` mapped to an explicit response model or the endpoint's return annotation. `response_model=None` produces `Response[Any]`; annotated raw responses and no-body status codes do not generate a Zodiac envelope schema.

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
