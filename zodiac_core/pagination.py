from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class PageParams(BaseModel):
    """
    Standard pagination query parameters.

    Usage:
        from typing import Annotated
        from fastapi import Query
        from zodiac_core.pagination import PageParams

        @app.get("/users")
        def list_users(page_params: Annotated[PageParams, Query()]):
            skip = (page_params.page - 1) * page_params.size
            limit = page_params.size
            ...
    """
    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Page size")


class PagedResponse(BaseModel, Generic[T]):
    """
    Standard generic paginated response model.

    Usage:
        from typing import Annotated
        from fastapi import Query
        from zodiac_core.pagination import PagedResponse, PageParams

        @app.get("/users", response_model=PagedResponse[UserSchema])
        def list_users(page_params: Annotated[PageParams, Query()]):
            users, total_count = db.find_users(...)
            return PagedResponse.create(users, total_count, page_params)
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
        params: PageParams
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
            size=params.size
        )
