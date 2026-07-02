from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Type, TypeVar

try:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
except ImportError as e:
    raise ImportError(
        "SQLModel and SQLAlchemy[asyncio] are required to use the 'zodiac_core.db' module. "
        "Please install it with: pip install 'zodiac-core[sql]'"
    ) from e

from zodiac_core.db.session import DEFAULT_DB_NAME, db, manage_session
from zodiac_core.exceptions import BadRequestException
from zodiac_core.pagination import PagedResponse, PageParams, SortParams, SortSpec

T = TypeVar("T")


class BaseSQLRepository:
    """
    Standard base class for SQL-based repositories.

    Supports multiple database instances via `db_name` and provides
    professional utilities for common operations like pagination.
    """

    sort_spec: SortSpec | None = None

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        db_name: str = DEFAULT_DB_NAME,
        options: Optional[Any] = None,
    ) -> None:
        """
        Initialize the repository.

        Args:
            session_factory: Optional custom session factory. If provided, db_name is ignored.
            db_name: The name of the database engine registered in db.setup(). Defaults to DEFAULT_DB_NAME ("default").
            options: Optional configuration/options for the repository.
        """
        self._session_factory = session_factory
        self.db_name = db_name
        self.options = options

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Async context manager for obtaining a database session.
        Uses the injected factory or resolves one from the global 'db' via 'db_name'.

        Note:
            This context manager does NOT auto-commit. You must explicitly call
            `await session.commit()` to persist changes to the database.
        """
        factory = self._session_factory or db.get_factory(self.db_name)
        async with manage_session(factory) as session:
            yield session

    async def paginate(
        self,
        session: AsyncSession,
        statement: Any,
        params: PageParams,
        transformer: Optional[Type[T]] = None,
        *,
        sort_spec: SortSpec | None = None,
    ) -> PagedResponse[T]:
        """
        Execute a paginated query with automatic count and paging.

        Performs:
        1. Optional multi-column sorting using public field mappings.
        2. Automatic total count query using the provided statement.
        3. Automatic limit/offset application.
        4. Packaging results into a standardized PagedResponse.

        Args:
            session: The active AsyncSession.
            statement: The SQLAlchemy select statement (without limit/offset).
            params: Standard PageParams (page, size).
            transformer: Optional Pydantic model to transform DB objects into.
            sort_spec: Optional reusable sort configuration. When omitted, the
                repository class-level ``sort_spec`` is used.

        Example:
            ```python
            async with self.session() as session:
                stmt = select(UserModel).order_by(UserModel.created_at.desc())
                return await self.paginate(session, stmt, params)
            ```
        """
        effective_sort_spec = sort_spec or self.sort_spec

        if effective_sort_spec is not None:
            sort_params = params if isinstance(params, SortParams) else None
            statement = self.apply_sorting(statement, sort_params, sort_spec=effective_sort_spec)

        # 1. Execute Count Query
        # Remove limit/offset/order_by (if any) for count query, then wrap in subquery.
        # Wrapping in subquery handles complex queries (joins, groups).
        count_base = statement.limit(None).offset(None).order_by(None)
        count_stmt = select(func.count()).select_from(count_base.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # 2. Execute Paged Query
        skip = (params.page - 1) * params.size
        paged_stmt = statement.offset(skip).limit(params.size)
        result = await session.execute(paged_stmt)
        items = result.scalars().all()

        # 3. Optional Transformation
        if transformer:
            items = [transformer.model_validate(item) for item in items]

        return PagedResponse.create(items=list(items), total=total, params=params)

    def apply_sorting(
        self,
        statement: Any,
        sort_params: SortParams | None = None,
        *,
        sort_spec: SortSpec | None = None,
    ) -> Any:
        """
        Apply validated multi-column sorting to a SQLAlchemy statement.
        Existing ORDER BY clauses are replaced when sort fields are present.

        Args:
            statement: The SQLAlchemy select statement to sort.
            sort_params: Standard SortParams or PageSortParams. When omitted,
                only the configured default sort is applied.
            sort_spec: Optional reusable sort configuration. When omitted, the
                repository class-level ``sort_spec`` is used.

        Example:
            ```python
            stmt = self.apply_sorting(
                select(UserModel),
                params,
                sort_spec=SortSpec(
                    columns={
                        "name": UserModel.name,
                        "created_at": UserModel.created_at,
                    }
                ),
            )
            ```
        """
        if sort_params is not None and not isinstance(sort_params, SortParams):
            raise TypeError("sort_params must be SortParams or PageSortParams")

        effective_sort_spec = sort_spec or self.sort_spec

        if effective_sort_spec is None:
            return statement

        sort_pairs = effective_sort_spec.pairs_for(sort_params)
        if not sort_pairs:
            return statement

        order_by_clauses = []
        for field, direction in sort_pairs:
            column = effective_sort_spec.columns.get(field)
            if column is None:
                raise BadRequestException(message=f"Unsupported sort field: {field}")
            order_by_clauses.append(column.asc() if direction == "asc" else column.desc())

        return statement.order_by(None).order_by(*order_by_clauses)

    async def paginate_query(
        self,
        statement: Any,
        params: PageParams,
        transformer: Optional[Type[T]] = None,
        *,
        sort_spec: SortSpec | None = None,
    ) -> PagedResponse[T]:
        """
        Convenience method that automatically manages session for pagination.

        This is a wrapper around `paginate()` that handles session management,
        making it easier to use in repository methods.

        Args:
            statement: The SQLAlchemy select statement (without limit/offset).
            params: Standard PageParams (page, size).
            transformer: Optional Pydantic model to transform DB objects into.
            sort_spec: Optional reusable sort configuration. When omitted, the
                repository class-level ``sort_spec`` is used.

        Example:
            ```python
            async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
                stmt = select(ItemModel).order_by(ItemModel.id)
                return await self.paginate_query(stmt, params)
            ```
        """
        async with self.session() as session:
            return await self.paginate(
                session,
                statement,
                params,
                transformer,
                sort_spec=sort_spec,
            )
