from dataclasses import dataclass
from dataclasses import field as dataclass_field
from types import MappingProxyType
from typing import Any, Generic, List, Literal, Mapping, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")
SortDirection = Literal["asc", "desc"]
SortPair = tuple[str, SortDirection]
SortExpression = str | SortPair


class PageParams(BaseModel):
    """
    Standard pagination query parameters.

    Usage:
        ```python
        from typing import Annotated
        from fastapi import Query
        from zodiac_core.pagination import PageParams

        @app.get("/users")
        def list_users(page_params: Annotated[PageParams, Query()]):
            skip = (page_params.page - 1) * page_params.size
            limit = page_params.size
            ...
        ```
    """

    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Page size")


class _SortItem(BaseModel):
    """
    Internal representation parsed from query strings like `name:asc`.
    """

    field: str = Field(min_length=1, description="Sortable field name")
    direction: SortDirection = Field("asc", description="Sort direction")

    @classmethod
    def parse(cls, expression: str) -> "_SortItem":
        expression = expression.strip()
        field, separator, direction = expression.partition(":")
        data = {"field": field.strip()}
        if separator:
            data["direction"] = direction.strip().lower()
        return cls.model_validate(data)


def _parse_sort_items(expressions: Sequence[str]) -> List[_SortItem]:
    return [_SortItem.parse(expression) for expression in expressions]


def _coerce_sort_expression(expression: SortExpression) -> List[SortPair]:
    if isinstance(expression, tuple):
        field, direction = expression
        item = _SortItem.model_validate({"field": field, "direction": direction})
        return [(item.field, item.direction)]
    return [(item.field, item.direction) for item in _parse_sort_items([expression])]


@dataclass(frozen=True)
class SortSpec:
    """
    Reusable sorting configuration for repository list queries.

    ``columns`` is an explicit whitelist from public API field names to
    SQLAlchemy column/expression objects. ``default`` is used when the request
    does not include a sort parameter.

    Example:
        ```python
        class ItemRepository(BaseSQLRepository):
            sort_spec = SortSpec(
                columns={
                    "name": ItemModel.name,
                    "created_at": ItemModel.created_at,
                },
                default=["created_at:desc", "name:asc"],
            )
        ```
    """

    columns: Mapping[str, Any]
    default: Sequence[SortExpression] = dataclass_field(default_factory=tuple)

    def __post_init__(self) -> None:
        columns = MappingProxyType(dict(self.columns))
        default_pairs = tuple(pair for expression in self.default for pair in _coerce_sort_expression(expression))
        unknown_defaults = [field for field, _ in default_pairs if field not in columns]
        if unknown_defaults:
            unknown = ", ".join(sorted(set(unknown_defaults)))
            raise ValueError(f"Default sort field is not configured in SortSpec.columns: {unknown}")

        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "_default_pairs", default_pairs)

    @property
    def default_pairs(self) -> List[SortPair]:
        """Parsed default sort fields."""
        return list(self._default_pairs)

    def pairs_for(self, sort_params: "SortParams | None") -> List[SortPair]:
        """Return request sort pairs when present; otherwise return defaults."""
        if sort_params is not None and sort_params.sort_pairs:
            return sort_params.sort_pairs
        return self.default_pairs


class SortParams(BaseModel):
    """
    Standard multi-column sorting query parameters.

    FastAPI maps repeated `sort` query parameters into the list:
    `?sort=name:asc&sort=created_at:desc`.
    """

    sort: List[str] = Field(
        default_factory=list,
        description='Sort expressions in "field:direction" format, for example "name:asc".',
    )

    @field_validator("sort")
    @classmethod
    def validate_sort_expressions(cls, values: List[str]) -> List[str]:
        _parse_sort_items(values)
        return values

    @property
    def sort_pairs(self) -> List[SortPair]:
        """
        Parsed sort fields for consumers that do not use repository helpers.
        """
        return [(item.field, item.direction) for item in _parse_sort_items(self.sort)]


class PageSortParams(PageParams, SortParams):
    """
    Combined pagination and sorting query parameters.
    """


class PagedResponse(BaseModel, Generic[T]):
    """
    Standard generic paginated response model.

    Usage:
        ```python
        from typing import Annotated
        from fastapi import Query
        from zodiac_core.pagination import PagedResponse, PageParams

        @app.get("/users", response_model=PagedResponse[UserSchema])
        def list_users(page_params: Annotated[PageParams, Query()]):
            users, total_count = db.find_users(...)
            return PagedResponse.create(users, total_count, page_params)
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    items: List[T] = Field(description="List of items for the current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Current page size")

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        params: PageParams,
    ) -> "PagedResponse[T]":
        """
        Factory method to create a PagedResponse from items, total count, and PageParams.

        Args:
            items: The list of data objects (Pydantic models or dicts).
            total: The total number of records in the database matching the query.
            params: The PageParams object from the request.
        """
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
        )
