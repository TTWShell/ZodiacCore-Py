from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, BeforeValidator


def ensure_utc(v: Any) -> Any:
    """
    Ensure a datetime object is timezone-aware (UTC).
    If it's naive (from SQLite), attach UTC.
    If it's already aware, convert to UTC.
    """
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)
    return v


# Reusable UTC Datetime type with automatic conversion
UtcDatetime = Annotated[datetime, BeforeValidator(ensure_utc)]


class CoreModel(BaseModel):
    """
    Base Pydantic model for all Zodiac schemas (DTOs).

    Features:
    - Standard snake_case fields
    - From attributes enabled (ORM mode)
    """
    model_config = ConfigDict(
        from_attributes=True,
    )


class DateTimeSchemaMixin(BaseModel):
    """Mixin for models that include standard timestamps."""
    created_at: UtcDatetime = Field(
        ...,
        description="The UTC timestamp when the record was created."
    )
    updated_at: UtcDatetime = Field(
        ...,
        description="The UTC timestamp when the record was last updated."
    )


class IntIDSchemaMixin(BaseModel):
    """Mixin for models that include an integer ID."""
    id: int = Field(
        ...,
        description="The unique integer identifier."
    )


class UUIDSchemaMixin(BaseModel):
    """Mixin for models that include a UUID."""
    id: UUID = Field(
        ...,
        description="The unique UUID identifier."
    )


class IntIDSchema(CoreModel, IntIDSchemaMixin, DateTimeSchemaMixin):
    """
    Base schema for models with an Integer ID and Timestamps.
    Includes: Core Config + ID + CreatedAt + UpdatedAt.
    """
    pass


class UUIDSchema(CoreModel, UUIDSchemaMixin, DateTimeSchemaMixin):
    """
    Base schema for models with a UUID and Timestamps.
    Includes: Core Config + ID + CreatedAt + UpdatedAt.
    """
    pass
