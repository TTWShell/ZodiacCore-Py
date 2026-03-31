from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlmodel import SQLModel
except ImportError as e:
    raise ImportError(
        "SQLModel and SQLAlchemy[asyncio] are required to use the 'zodiac_core.db' module. "
        "Please install it with: pip install 'zodiac-core[sql]'"
    ) from e

# Global constant for the default database name
DEFAULT_DB_NAME = "default"


@asynccontextmanager
async def manage_session(factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """
    Standardizes the lifecycle management of an AsyncSession.
    Ensures rollback on error and proper closure.

    Note:
        This context manager does NOT auto-commit. You must explicitly call
        `await session.commit()` to persist changes to the database.

    Example:
        ```python
        async with manage_session(factory) as session:
            session.add(user)
            await session.commit()  # Required to persist changes
        ```
    """
    session: AsyncSession = factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


class DatabaseManager:
    """
    Manages multiple Async Database Engines and Session Factories.
    Implemented as a Strict Singleton to coordinate connection pools.

    Integration Examples:

    1. **Native FastAPI (Lifespan + Depends):**

        ```python
        # main.py
        from contextlib import asynccontextmanager
        from fastapi import FastAPI, Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from zodiac_core.db.session import db, get_session

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            db.setup("sqlite+aiosqlite:///database.db")
            yield
            await db.shutdown()

        app = FastAPI(lifespan=lifespan)

        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            return {"status": "ok"}
        ```

    2. **Dependency Injector (Using provided init_db_resource):**

        ```python
        # containers.py
        from dependency_injector import containers, providers
        from zodiac_core.utils import strtobool
        from zodiac_core.db.session import init_db_resource

        class Container(containers.DeclarativeContainer):
            config = providers.Configuration(strict=True)

            # Use the pre-built resource helper
            db_manager = providers.Resource(
                init_db_resource,
                database_url=config.db.url,
                echo=config.db.echo.as_(strtobool),
            )
        ```
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines: Dict[str, AsyncEngine] = {}
            cls._instance._session_factories: Dict[str, async_sessionmaker[AsyncSession]] = {}
            cls._instance._setup_configs: Dict[str, Dict[str, Any]] = {}
        return cls._instance

    def get_engine(self, name: str = DEFAULT_DB_NAME) -> AsyncEngine:
        """Access a specific SQLAlchemy AsyncEngine by name."""
        if name not in self._engines:
            raise RuntimeError(f"Database engine '{name}' is not initialized. Call db.setup(name='{name}') first.")
        return self._engines[name]

    def get_factory(self, name: str = DEFAULT_DB_NAME) -> async_sessionmaker[AsyncSession]:
        """Access a specific AsyncSession factory by name."""
        if name not in self._session_factories:
            raise RuntimeError(f"Session factory for '{name}' is not initialized. Call db.setup(name='{name}') first.")
        return self._session_factories[name]

    @property
    def engine(self) -> AsyncEngine:
        """Access the default SQLAlchemy AsyncEngine."""
        return self.get_engine(DEFAULT_DB_NAME)

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Access the default AsyncSession factory."""
        return self.get_factory(DEFAULT_DB_NAME)

    def setup(
        self,
        database_url: str,
        name: str = DEFAULT_DB_NAME,
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_pre_ping: bool = True,
        connect_args: Optional[dict] = None,
        **kwargs,
    ) -> None:
        """Initialize an Async Engine and Session Factory with a specific name."""
        engine_args = {
            "echo": echo,
            "pool_pre_ping": pool_pre_ping,
            "connect_args": connect_args or {},
            **kwargs,
        }

        if "sqlite" not in database_url:
            engine_args["pool_size"] = pool_size
            engine_args["max_overflow"] = max_overflow

        current = {
            "database_url": database_url,
            "engine_args": deepcopy(engine_args),
        }

        if name in self._engines:
            existing = self._setup_configs.get(name)
            if existing == current:
                logger.debug(f"Database '{name}' is already configured with the same settings, skipping.")
                return
            raise RuntimeError(f"Database '{name}' is already configured with different settings")

        engine = create_async_engine(database_url, **engine_args)
        factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._engines[name] = engine
        self._session_factories[name] = factory
        self._setup_configs[name] = current
        logger.info(f"Database '{name}' initialized successfully.")

    async def shutdown(self, name: str | None = None) -> None:
        """
        Dispose database resources.

        Args:
            name: Optional database name. When provided, only that engine/factory
                  is disposed. When omitted, all registered databases are disposed.
        """
        if name is not None:
            engine = self._engines.pop(name, None)
            self._session_factories.pop(name, None)
            self._setup_configs.pop(name, None)
            if engine is not None:
                await engine.dispose()
            return

        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
        self._session_factories.clear()
        self._setup_configs.clear()

    @asynccontextmanager
    async def session(self, name: str = DEFAULT_DB_NAME) -> AsyncGenerator[AsyncSession, None]:
        """
        Context Manager for obtaining a NEW database session from a specific engine.

        Note:
            This context manager does NOT auto-commit. You must explicitly call
            `await session.commit()` to persist changes to the database.

        Example:
            ```python
            async with db.session() as session:
                session.add(user)
                await session.commit()  # Required to persist changes
            ```
        """
        async with manage_session(self.get_factory(name)) as session:
            yield session

    async def verify(self, name: str = DEFAULT_DB_NAME) -> bool:
        """
        Verify the database connection is working.

        Args:
            name: The database name to verify.

        Returns:
            True if connection is successful.

        Raises:
            RuntimeError: If the database is not initialized.
            Exception: If the connection test fails.
        """
        async with self.session(name) as session:
            await session.execute(text("SELECT 1"))
        logger.info(f"Database '{name}' connection verified.")
        return True

    async def create_all(self, name: str = DEFAULT_DB_NAME, metadata: Any = None) -> None:
        """
        Create tables in the database.

        Args:
            name: The database name to create tables in.
            metadata: SQLAlchemy MetaData object. If None, uses SQLModel.metadata
                      which includes ALL registered models. For production, consider
                      using Alembic migrations instead.

        Example:
            ```python
            # Development: create all tables
            await db.create_all()

            # With custom metadata (only specific tables)
            from sqlalchemy import MetaData
            my_metadata = MetaData()
            await db.create_all(metadata=my_metadata)
            ```
        """
        target_metadata = metadata if metadata is not None else SQLModel.metadata
        async with self.get_engine(name).begin() as conn:
            await conn.run_sync(target_metadata.create_all)


# Global instance
db = DatabaseManager()


async def get_session(name: str = DEFAULT_DB_NAME) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI Dependency for obtaining a database session.

    Note:
        This dependency does NOT auto-commit. You must explicitly call
        `await session.commit()` within your endpoint to persist changes.

    Example:
        ```python
        # Default database — use directly as a dependency
        @app.post("/users")
        async def create_user(session: AsyncSession = Depends(get_session)):
            session.add(User(name="test"))
            await session.commit()
            return user

        # Named database — wrap in a thin dependency
        async def analytics_session():
            async for s in get_session("analytics"):
                yield s

        @app.get("/reports")
        async def get_reports(session: AsyncSession = Depends(analytics_session)):
            ...
        ```
    """
    async with db.session(name) as session:
        yield session


async def init_db_resource(
    database_url: str,
    name: str = DEFAULT_DB_NAME,
    echo: bool = False,
    connect_args: Optional[dict] = None,
    **kwargs,
) -> AsyncGenerator[DatabaseManager, None]:
    """
    A helper for dependency_injector's Resource provider.
    Handles the setup and shutdown lifecycle of the global `db` instance.
    Cleanup is scoped to the provided database `name`, so other registered
    databases remain available.
    """
    db.setup(database_url=database_url, name=name, echo=echo, connect_args=connect_args, **kwargs)
    try:
        yield db
    finally:
        await db.shutdown(name=name)
