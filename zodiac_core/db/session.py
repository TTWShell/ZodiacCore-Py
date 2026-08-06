from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Annotated, Any, AsyncGenerator, Callable, Dict, NoReturn, Optional

from fastapi.exceptions import FastAPIError
from fastapi.params import Depends as DependsParameter
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
        """Open a managed session for code that owns a unit of work.

        This is the general lifecycle API for background jobs, CLI commands,
        startup tasks, and services or repositories that own their unit of
        work. At the FastAPI boundary, ``get_session`` or a dependency returned
        by ``session_dependency`` may instead make the endpoint own the unit of
        work. Lower layers must never call those FastAPI dependency callables.
        If the endpoint owns the unit of work, pass the concrete
        ``AsyncSession`` to participating services and repositories; otherwise
        let the service or repository use this context manager or
        ``BaseSQLRepository.session()``.

        Each context creates a new ``AsyncSession`` and always closes it. The
        session borrows a connection lazily from the selected engine's pool;
        closing the session returns that connection to the pool. Exceptions
        trigger a rollback. Successful exit does not commit automatically.

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


def _default_database_name() -> str:
    """Return the server-controlled database name used by ``Depends(get_session)``."""
    return DEFAULT_DB_NAME


class _RejectDatabaseNameRequestBinding:
    """Reject attempts to model the server-controlled name as request data.

    FastAPI skips Pydantic field creation while the parameter default is a
    ``Depends`` instance. A keyword-bound ``partial`` replaces that default,
    which makes FastAPI build a request field and deliberately reaches this
    guard during route registration.
    """

    def __get_pydantic_core_schema__(self, _source_type: Any, _handler: Any) -> NoReturn:
        raise FastAPIError(
            "partial(get_session, ...) is unsupported for FastAPI dependencies; use session_dependency(name) instead"
        )

    def __repr__(self) -> str:
        return "ServerControlledDatabaseName()"


class _DefaultDatabaseName(str, DependsParameter):
    """Act as ``'default'`` to callers and a private dependency to FastAPI.

    The dual role preserves the published direct-call signature and behavior
    while keeping ``Depends(get_session)`` free of request-controlled input.
    """

    def __new__(cls, _value: str = DEFAULT_DB_NAME) -> "_DefaultDatabaseName":
        # ``copy``, ``deepcopy``, and pickle reconstruct ``str`` subclasses by
        # passing their string value back to ``__new__``.
        return str.__new__(cls, DEFAULT_DB_NAME)

    def __init__(self, _value: str = DEFAULT_DB_NAME) -> None:
        DependsParameter.__init__(self, dependency=_default_database_name)


_DEFAULT_DATABASE_NAME_PARAMETER = _DefaultDatabaseName()
_ServerControlledDatabaseName = Annotated[str, _RejectDatabaseNameRequestBinding()]


async def get_session(
    name: _ServerControlledDatabaseName = _DEFAULT_DATABASE_NAME_PARAMETER,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a managed session while preserving the public named-call API.

    At the FastAPI API/DI boundary, use ``Depends(get_session)`` only for the
    default database. FastAPI resolves ``name`` through a private dependency,
    so it is not exposed as request input.

    The optional ``name`` argument remains source- and call-compatible with the
    public API introduced in ZodiacCore 0.7.0, including existing server-side
    wrapper dependencies that iterate ``get_session("analytics")``. New named
    FastAPI wiring should use ``session_dependency(name)`` so FastAPI directly
    manages exception propagation and cleanup. Never use
    ``partial(get_session, ...)``. Keyword-bound partials are rejected during
    route registration because FastAPI would otherwise override the bound
    database name while resolving dependencies.

    Services, repositories, jobs, and CLI commands should not treat this
    FastAPI-oriented generator as their general session API. If the endpoint
    owns a unit of work, pass its concrete ``AsyncSession`` to participating
    lower layers. Otherwise use ``db.session(...)`` or
    ``BaseSQLRepository.session()`` at the layer that owns the unit of work.

    By default, FastAPI resolves this dependency callable once per request, so
    repeated uses in that request share one ``AsyncSession``; a later request
    gets a new session. The session is not a pooled connection: it borrows a
    connection lazily from the selected engine's pool and returns it during
    cleanup.

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
        ```
    """
    async with db.session(name) as session:
        yield session


def session_dependency(name: str) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """Create a request-parameter-free dependency bound to a named database.

    This is a FastAPI dependency factory, not a session factory or context
    manager. Call it once while defining API wiring, then pass the returned
    callable to ``Depends``. Calling this factory creates neither an
    ``AsyncSession`` nor a database connection. FastAPI creates the
    ``AsyncSession`` when it resolves the returned dependency; a pooled
    connection is normally checked out only when database work begins.

    The database name must be fixed by server-side application code. Never
    derive it from a query parameter, path parameter, header, request body, or
    any other request data.

    Do not pass ``session_dependency`` itself to ``Depends``: FastAPI would
    treat ``name`` as a required request parameter and, if supplied, inject the
    returned callable instead of an ``AsyncSession``. Do not use
    ``partial(get_session, ...)``; keyword-bound partials fail during route
    registration instead of risking a silent connection to the wrong database.
    Existing server-side wrapper dependencies that iterate
    ``get_session(name)`` remain source-compatible, but new named FastAPI routes
    should use this factory for direct exception propagation and cleanup. Do not
    manually call or iterate the returned dependency from business code; lower
    layers that own a unit of work use ``db.session(name)`` or
    ``BaseSQLRepository.session()`` instead.

    Create and store one named dependency at module or router scope. FastAPI
    dependency caching and ``app.dependency_overrides`` identify dependencies
    by callable identity, so pass the stored callable everywhere instead of
    repeatedly calling this factory.

    Args:
        name: Database name registered with ``db.setup(..., name=name)``.

    Returns:
        A FastAPI-safe async-generator dependency. By default, FastAPI creates
        one ``AsyncSession`` for this callable per request; repeated uses of the
        stored callable share that session. Named dependencies are zero-argument
        closures. Passing ``DEFAULT_DB_NAME`` returns ``get_session`` itself so
        default-database dependency caching and overrides remain unified.

    Example:
        ```python
        get_analytics_session = session_dependency("analytics")

        @app.get("/reports")
        async def get_reports(
            session: AsyncSession = Depends(get_analytics_session),
        ):
            ...
        ```
    """
    if name == DEFAULT_DB_NAME:
        return get_session

    async def get_named_session() -> AsyncGenerator[AsyncSession, None]:
        async with db.session(name) as session:
            yield session

    return get_named_session


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
