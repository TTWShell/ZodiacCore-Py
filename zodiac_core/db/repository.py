from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zodiac_core.db.session import DEFAULT_DB_NAME, db, manage_session


class BaseSQLRepository:
    """
    Standard base class for SQL-based repositories.

    Supports multiple database instances via `db_name`.
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
        """
        factory = self._session_factory or db.get_factory(self.db_name)
        async with manage_session(factory) as session:
            yield session
