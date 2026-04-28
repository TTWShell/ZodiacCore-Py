# Exception Handling

ZodiacCore provides a centralized exception handling system that automatically converts Python exceptions into standardized, production-ready JSON responses.

## 1. Core Concepts

### The ZodiacException Base
Business logic errors should inherit from `ZodiacException` directly or from one of the built-in exception families. This base class allows you to define:

- **`http_code`**: The HTTP status code (e.g., 404, 400).
- **`code`**: A custom business error code.
- **`message`**: A human-readable error description.
- **`data`**: Optional payload for additional error details (e.g., validation errors).

`http_code` controls the HTTP response status. `code` is the business error code in the response body; it can differ from the HTTP status.

### Automatic Transformation
When a `ZodiacException` is raised, the `handler_zodiac_exception` exception handler catches it and transforms it into a standard JSON response:

```json
{
  "code": 404,
  "message": "Resource not found",
  "data": null
}
```

---

## 2. Validation Errors (HTTP 422)

One of the best features of ZodiacCore is that it also standardizes framework-level validation errors. When a user sends invalid JSON or missing parameters, FastAPI normally returns a custom structure. ZodiacCore catches these and wraps them in our standard format:

```json
{
  "code": 422,
  "message": "Unprocessable Entity",
  "data": [
    {
      "type": "missing",
      "loc": ["body", "username"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

This ensures your API is 100% consistent, whether the error came from your business logic or from a schema mismatch.

---

## 3. Built-in Exceptions

ZodiacCore includes several common exceptions ready to use:

| Exception | HTTP Status | Use Case |
| :--- | :--- | :--- |
| `BadRequestException` | 400 | Invalid input or parameters. |
| `UnauthorizedException` | 401 | Missing or invalid authentication. |
| `ForbiddenException` | 403 | Insufficient permissions. |
| `NotFoundException` | 404 | Resource does not exist. |
| `ConflictException` | 409 | Resource state conflict (e.g., duplicate entry). |
| `UnprocessableEntityException` | 422 | Business/semantic validation failed (entity well-formed but not processable). |
| `UpstreamServiceError` | 400 | A third-party/upstream service failed, timed out, or returned an unexpected status. |
| `UpstreamRequestError` | 400 | The upstream service rejected this service's request, usually HTTP 400 or 422. |

Built-in exception families have fixed HTTP statuses. If you subclass `BadRequestException`, the response status remains HTTP 400; overriding `http_code` on that subclass does not change the family status. Use `code` for business-specific error codes inside the response body.

---

## 4. Upstream Service Errors

Use `translate_upstream_errors` around third-party `httpx` calls to convert known upstream failures into standardized ZodiacCore exceptions. The decorated function should call `response.raise_for_status()` so non-2xx responses can be classified.

```python
from zodiac_core.http import ZodiacClient, translate_upstream_errors


@translate_upstream_errors(service="identity_and_access")
async def get_permissions(client: ZodiacClient):
    response = await client.post("/api/auth/by_user_id", json={"user_id": "..."})
    response.raise_for_status()
    return response.json()
```

Classification:

- Upstream HTTP 400 or 422 becomes `UpstreamRequestError`.
- Other upstream HTTP status failures become `UpstreamServiceError`.
- Other `httpx.RequestError` failures become `UpstreamServiceError`.

These upstream exceptions are part of ZodiacCore's built-in exception hierarchy and standard exception registration:

```python
from fastapi import FastAPI
from zodiac_core.exception_handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

With the standard handlers registered, unhandled upstream exceptions return HTTP 400 and are not treated as uncaught HTTP 500 errors from the current service. If your service catches `UpstreamServiceError` or `UpstreamRequestError` itself, that local handling wins and the global handler is not involved.

---

## 5. Custom Exceptions

For a business error that belongs to a built-in HTTP status family, subclass the built-in exception and set a business `code`, `message`, and optional `data`:

```python
from zodiac_core.exceptions import BadRequestException

class InsufficientBalanceException(BadRequestException):
    def __init__(self, current_balance: float):
        super().__init__(
            code=1001,  # Business error code; HTTP status stays 400
            message="Your account balance is too low.",
            data={"current_balance": current_balance},
        )
```

For a custom HTTP status that is not covered by the built-in exception families, inherit directly from `ZodiacException` and define `http_code`:

```python
from fastapi import status
from zodiac_core.exceptions import ZodiacException

class RateLimitedException(ZodiacException):
    http_code = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, retry_after: int):
        super().__init__(
            code=2001,
            message="Too many requests.",
            data={"retry_after": retry_after},
        )
```

Usage in a route:
```python
@app.post("/transfer")
async def transfer_money(amount: float):
    if amount > user.balance:
        raise InsufficientBalanceException(user.balance)
    ...
```

If a direct `ZodiacException` subclass does not define `http_code`, it inherits the default HTTP 500 status.

---

## 6. Integration

To enable global exception handling in your FastAPI app, use `register_exception_handlers`. This will catch:

1. All `ZodiacException` subclasses.
2. Pydantic `ValidationError` and FastAPI `RequestValidationError` (mapped to 422).
3. Upstream errors produced by `translate_upstream_errors` (mapped to 400).
4. Any uncaught `Exception` (mapped to 500 with secure logging).

```python
from fastapi import FastAPI
from zodiac_core.exception_handlers import register_exception_handlers

app = FastAPI()
register_exception_handlers(app)
```

---

## 7. API Reference

### Exception Base & Subclasses
::: zodiac_core.exceptions
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - ZodiacException
        - BadRequestException
        - UnauthorizedException
        - ForbiddenException
        - NotFoundException
        - ConflictException
        - UnprocessableEntityException
        - UpstreamServiceError
        - UpstreamRequestError

### Global Handler Registration
::: zodiac_core.exception_handlers
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - register_exception_handlers

### Upstream HTTP Decorators
::: zodiac_core.http
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - translate_upstream_errors
