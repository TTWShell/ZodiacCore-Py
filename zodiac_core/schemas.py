from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CoreModel(BaseModel):
    """
    Base Pydantic model for all Zodiac schemas (DTOs).

    Features:
    - Standard snake_case fields (default Pydantic behavior)
    - From attributes enabled (ORM mode)
    """
    model_config = ConfigDict(
        from_attributes=True,
    )


class DateTimeSchemaMixin(BaseModel):
    """Mixin for models that include standard timestamps."""
    created_at: datetime = Field(description="The UTC timestamp when the record was created.")
    updated_at: datetime = Field(description="The UTC timestamp when the record was last updated.")


class IntIDSchemaMixin(BaseModel):
    """Mixin for models that include an integer ID."""
    id: int = Field(description="The unique integer identifier.")


class UUIDSchemaMixin(BaseModel):
    """Mixin for models that include a UUID."""
    id: UUID = Field(description="The unique UUID identifier.")
