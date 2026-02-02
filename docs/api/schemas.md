# Data Schemas (DTOs)

ZodiacCore provides a set of base Pydantic models and types to standardize Data Transfer Objects (DTOs). These mirror our database models to ensure end-to-end consistency.

## 1. Core Models

### CoreModel
The `CoreModel` is the recommended base class for all your Pydantic models. It comes pre-configured with:
- **`from_attributes=True`**: Allows easy conversion from ORM objects (like SQLModel or SQLAlchemy) using `Model.model_validate(orm_obj)`.

```python
from zodiac_core import CoreModel

class UserSchema(CoreModel):
    username: str
    email: str
```

---

## 2. Standard Schema Mixins

We provide several mixins to match the `IntIDModel` and `UUIDModel` found in the database layer.

| Schema | Primary Key | Timestamps |
| :--- | :--- | :--- |
| `IntIDSchema` | `id: int` | `created_at`, `updated_at` |
| `UUIDSchema` | `id: UUID` | `created_at`, `updated_at` |

### Example Usage
```python
from zodiac_core import IntIDSchema

class ProductRead(IntIDSchema):
    name: str
    price: float
```

---

## 3. UTC Datetime Utility

Handling timezones correctly is notoriously difficult. ZodiacCore includes a `UtcDatetime` type that automatically converts incoming datetime objects to UTC and ensures they are timezone-aware.

```python
from zodiac_core import UtcDatetime
from pydantic import BaseModel

class Event(BaseModel):
    # Any incoming datetime will be converted to aware-UTC
    happened_at: UtcDatetime
```

---

## 4. API Reference

### Base Schemas
::: zodiac_core.schemas
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - CoreModel
        - IntIDSchema
        - UUIDSchema
        - UtcDatetime
        - IntIDSchemaMixin
        - UUIDSchemaMixin
        - DateTimeSchemaMixin
