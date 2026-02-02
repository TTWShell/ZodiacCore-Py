import uuid
from datetime import datetime, timezone
from typing import Optional

try:
    from sqlalchemy import DateTime, event
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.orm import Session
    from sqlalchemy.sql import expression
    from sqlmodel import Field, SQLModel
except ImportError as e:
    raise ImportError(
        "SQLModel is required to use the 'zodiac_core.db.sql' module. "
        "Please install it with: pip install 'zodiac-core[sql]'"
    ) from e


def utc_now() -> datetime:
    """Helper to get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class utcnow(expression.FunctionElement):
    type = DateTime(timezone=True)
    inherit_cache = True


@compiles(utcnow, "postgresql")
def pg_utcnow(element, compiler, **kw):
    return "timezone('utc', now())"


@compiles(utcnow, "mysql")
def mysql_utcnow(element, compiler, **kw):
    return "UTC_TIMESTAMP()"


@compiles(utcnow, "sqlite")
def sqlite_utcnow(element, compiler, **kw):
    return "datetime('now')"


class SQLDateTimeMixin(SQLModel):
    """
    Mixin for created_at and updated_at with SQLAlchemy server-side defaults.
    Supports PostgreSQL, MySQL, and SQLite with proper UTC handling.
    """

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={
            "server_default": utcnow(),
            "nullable": False,
        },
        sa_type=DateTime(timezone=True),
        description="Record creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={
            "server_default": utcnow(),
            "onupdate": utcnow(),
            "nullable": False,
        },
        sa_type=DateTime(timezone=True),
        description="Record last update timestamp (UTC)",
    )


@event.listens_for(Session, "before_flush")
def receive_before_flush(session, flush_context, instances):
    for obj in session.dirty:
        if hasattr(obj, "updated_at") and isinstance(obj, SQLDateTimeMixin):
            if session.is_modified(obj, include_collections=False):
                obj.updated_at = utc_now()


class SQLBase(SQLDateTimeMixin):
    """
    Base class for SQLModel models.
    Includes created_at and updated_at fields.
    """


class IntIDMixin(SQLModel):
    """Mixin for Integer primary key."""

    id: Optional[int] = Field(default=None, primary_key=True)


class UUIDMixin(SQLModel):
    """Mixin for UUID primary key."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )


class IntIDModel(SQLBase, IntIDMixin):
    """
    Base SQLModel with Integer ID and Timestamps.
    Includes: ID (int) + CreatedAt + UpdatedAt.
    """


class UUIDModel(SQLBase, UUIDMixin):
    """
    Base SQLModel with UUID and Timestamps.
    Includes: ID (UUID) + CreatedAt + UpdatedAt.
    """
