from typing import AsyncGenerator
from contextlib import asynccontextmanager

try:
    from sqlmodel import SQLModel
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        create_async_engine,
        async_sessionmaker,
    )
except ImportError:
    raise ImportError(
        "SQLModel and SQLAlchemy[asyncio] are required to use the 'zodiac_core.db' module. "
        "Please install it with: pip install 'zodiac-core[sql]'"
    )


class DatabaseManager:
    """
    Manages the Async Database Engine and Session Factory.
    Implemented as a Strict Singleton to ensure only one Connection Pool exists.

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
        from zodiac_core.db.session import init_db_resource

        class Container(containers.DeclarativeContainer):
            config = providers.Configuration()

            # Use the pre-built resource helper
            db_manager = providers.Resource(
                init_db_resource,
                database_url=config.db.url,
                echo=config.db.echo.as_bool(),
            )
        ```
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize state only once during the first creation
            cls._instance._engine = None
            cls._instance._session_factory = None
        return cls._instance

    def setup(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_pre_ping: bool = True,
        **kwargs,
    ) -> None:
        """
        Initialize the Async Engine and Session Factory.
        """
        if self._engine:
            return

        engine_args = {
            "echo": echo,
            "pool_pre_ping": pool_pre_ping,
            **kwargs,
        }

        if "sqlite" not in database_url:
            engine_args["pool_size"] = pool_size
            engine_args["max_overflow"] = max_overflow

        self._engine = create_async_engine(database_url, **engine_args)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def shutdown(self) -> None:
        """Dispose of the engine and close all connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context Manager for obtaining a NEW database session."""
        if not self._session_factory:
            raise RuntimeError("DatabaseManager is not initialized. Call db.setup() first.")

        session: AsyncSession = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def create_all(self) -> None:
        """Create all tables defined in SQLModel metadata."""
        if not self._engine:
            raise RuntimeError("DatabaseManager is not initialized.")

        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)


# Global instance
db = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for obtaining a database session."""
    async with db.session() as session:
        yield session


async def init_db_resource(
    database_url: str,
    echo: bool = False,
    **kwargs,
) -> AsyncGenerator[DatabaseManager, None]:
    """
    A helper for dependency_injector's Resource provider.
    Handles the setup and shutdown lifecycle of the global `db` instance.
    """
    db.setup(database_url=database_url, echo=echo, **kwargs)
    yield db
    await db.shutdown()
