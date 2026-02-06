from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zodiac_core.db.session import DEFAULT_DB_NAME, db, manage_session
from zodiac_core.pagination import PagedResponse, PageParams

T = TypeVar("T")


class BaseSQLRepository:
    """
    Standard base class for SQL-based repositories.

    Supports multiple database instances via `db_name` and provides
    professional utilities for common operations like pagination.
    """

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
    ) -> PagedResponse[T]:
        """
        Execute a paginated query with automatic count and paging.

        Performs:
        1. Automatic total count query using the provided statement.
        2. Automatic limit/offset application.
        3. Packaging results into a standardized PagedResponse.

        Args:
            session: The active AsyncSession.
            statement: The SQLAlchemy select statement (without limit/offset).
            params: Standard PageParams (page, size).
            transformer: Optional Pydantic model to transform DB objects into.

        Example:
            ```python
            async with self.session() as session:
                stmt = select(UserModel).order_by(UserModel.created_at.desc())
                return await self.paginate(session, stmt, params)
            ```
        """
        # 1. Execute Count Query
        # Remove limit/offset (if any) for count query, then wrap in subquery
        # subquery() handles order_by correctly, and wrapping in subquery handles complex queries (joins, groups)
        count_base = statement.limit(None).offset(None)
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

    async def paginate_query(
        self,
        statement: Any,
        params: PageParams,
        transformer: Optional[Type[T]] = None,
    ) -> PagedResponse[T]:
        """
        Convenience method that automatically manages session for pagination.

        This is a wrapper around `paginate()` that handles session management,
        making it easier to use in repository methods.

        Args:
            statement: The SQLAlchemy select statement (without limit/offset).
            params: Standard PageParams (page, size).
            transformer: Optional Pydantic model to transform DB objects into.

        Example:
            ```python
            async def list_items(self, params: PageParams) -> PagedResponse[ItemModel]:
                stmt = select(ItemModel).order_by(ItemModel.id)
                return await self.paginate_query(stmt, params)
            ```
        """
        async with self.session() as session:
            return await self.paginate(session, statement, params, transformer)
