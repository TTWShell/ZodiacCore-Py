from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional

try:
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
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines: Dict[str, AsyncEngine] = {}
            cls._instance._session_factories: Dict[str, async_sessionmaker[AsyncSession]] = {}
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
        if name in self._engines:
            return

        engine_args = {
            "echo": echo,
            "pool_pre_ping": pool_pre_ping,
            "connect_args": connect_args or {},
            **kwargs,
        }

        if "sqlite" not in database_url:
            engine_args["pool_size"] = pool_size
            engine_args["max_overflow"] = max_overflow

        engine = create_async_engine(database_url, **engine_args)
        factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._engines[name] = engine
        self._session_factories[name] = factory

    async def shutdown(self) -> None:
        """Dispose of all registered engines and clear factories."""
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()
        self._session_factories.clear()

    @asynccontextmanager
    async def session(self, name: str = DEFAULT_DB_NAME) -> AsyncGenerator[AsyncSession, None]:
        """Context Manager for obtaining a NEW database session from a specific engine."""
        async with manage_session(self.get_factory(name)) as session:
            yield session

    async def create_all(self, name: str = DEFAULT_DB_NAME) -> None:
        """Create all tables defined in SQLModel metadata for a specific engine."""
        async with self.get_engine(name).begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)


# Global instance
db = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for obtaining a default database session."""
    async with db.session() as session:
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
    """
    db.setup(database_url=database_url, name=name, echo=echo, connect_args=connect_args, **kwargs)
    try:
        yield db
    finally:
        await db.shutdown()
