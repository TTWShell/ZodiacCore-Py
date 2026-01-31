import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlmodel import Field, SQLModel

from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.db.session import db

from .utils import DEFAULT_MYSQL_URL, DEFAULT_PG_URL


# Define specific models for multi-db test to avoid table name conflicts
class User(SQLModel, table=True):
    __tablename__ = "multi_users"
    id: int = Field(default=None, primary_key=True)
    name: str


class Product(SQLModel, table=True):
    __tablename__ = "multi_products"
    id: int = Field(default=None, primary_key=True)
    title: str


@pytest.mark.serial
class TestMultiDatabaseIntegration:
    """
    Integration tests for cross-database operations (PostgreSQL + MySQL).
    Verifies that the DatabaseManager correctly routes queries and manages pools.
    """

    @pytest_asyncio.fixture(autouse=True)
    async def setup_databases(self):
        """Initialize both PG and MySQL engines before each test."""
        if db._engines:
            await db.shutdown()

        pg_url = os.getenv("POSTGRES_URL", DEFAULT_PG_URL)
        mysql_url = os.getenv("MYSQL_URL", DEFAULT_MYSQL_URL)

        db.setup(pg_url, name="pg")
        db.setup(mysql_url, name="mysql")

        # Create tables in both databases
        async with db.get_engine("pg").begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with db.get_engine("mysql").begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        yield

        await db.shutdown()

    @pytest.mark.asyncio
    async def test_independent_routing_and_persistence(self):
        """
        Verify that data saved via one repo is NOT visible in the other,
        and that they persist to the correct physical backends.
        """
        pg_repo = BaseSQLRepository(db_name="pg")
        mysql_repo = BaseSQLRepository(db_name="mysql")

        # 1. Save to PG
        async with pg_repo.session() as session:
            session.add(User(name="pg_user"))
            await session.commit()

        # 2. Save to MySQL
        async with mysql_repo.session() as session:
            session.add(User(name="mysql_user"))
            await session.commit()

        # 3. Verify PG data (should only have pg_user)
        async with pg_repo.session() as session:
            res = await session.execute(text("SELECT name FROM multi_users"))
            names = res.scalars().all()
            assert "pg_user" in names
            assert "mysql_user" not in names

        # 4. Verify MySQL data (should only have mysql_user)
        async with mysql_repo.session() as session:
            res = await session.execute(text("SELECT name FROM multi_users"))
            names = res.scalars().all()
            assert "mysql_user" in names
            assert "pg_user" not in names

    @pytest.mark.asyncio
    async def test_repository_binding(self):
        """Verify that specialized repositories correctly bind to their target DBs."""

        class PgUserRepo(BaseSQLRepository):
            def __init__(self):
                super().__init__(db_name="pg")

        class MysqlUserRepo(BaseSQLRepository):
            def __init__(self):
                super().__init__(db_name="mysql")

        pg_repo = PgUserRepo()
        mysql_repo = MysqlUserRepo()

        # Assert engines are different
        async with pg_repo.session() as pg_session:
            async with mysql_repo.session() as mysql_session:
                # Compare engine driver names or internal URLs if possible
                assert "postgresql" in str(pg_session.bind.url)
                assert "mysql" in str(mysql_session.bind.url)

    @pytest.mark.asyncio
    async def test_global_shutdown_cleans_all_pools(self):
        """Verify that db.shutdown() disposes of all registered engines."""
        assert "pg" in db._engines
        assert "mysql" in db._engines

        await db.shutdown()

        assert not db._engines
        assert not db._session_factories

        with pytest.raises(RuntimeError, match="not initialized"):
            db.get_engine("pg")
