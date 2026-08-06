from contextlib import asynccontextmanager
from copy import deepcopy
from functools import partial
from inspect import signature
from typing import Annotated
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.exceptions import FastAPIError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel

from zodiac_core.db import session_dependency
from zodiac_core.db.session import (
    DEFAULT_DB_NAME,
    DatabaseManager,
    db,
    get_session,
    init_db_resource,
    manage_session,
)

from .utils import DB_URLS


class TestDatabaseManager:
    """Tests for the DatabaseManager singleton and its lifecycle."""

    @pytest.mark.asyncio
    async def test_singleton_behavior(self):
        """Ensure DatabaseManager is a strict singleton."""
        db1 = DatabaseManager()
        db2 = DatabaseManager()
        assert db1 is db2
        assert db1 is db

    @pytest.mark.asyncio
    async def test_property_guards(self):
        """Ensure engine and factory raise error if accessed before setup."""
        if db._engines:
            await db.shutdown()

        with pytest.raises(RuntimeError, match="Database engine 'default' is not initialized"):
            _ = db.engine

        with pytest.raises(RuntimeError, match="Session factory for 'default' is not initialized"):
            _ = db.session_factory

    @pytest.mark.parametrize("name, url, connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_lifecycle_setup_shutdown(self, name, url, connect_args):
        """Verify setup, idempotency, and shutdown state across different DBs."""
        if db._engines:
            await db.shutdown()

        # 1. Setup
        db.setup(url, connect_args=connect_args)
        assert DEFAULT_DB_NAME in db._engines
        assert DEFAULT_DB_NAME in db._session_factories
        assert db.engine is not None
        assert db.session_factory is not None

        # 2. Idempotency
        original_engine = db.engine
        db.setup(url, connect_args=connect_args)
        assert db.engine is original_engine

        # 3. Shutdown
        await db.shutdown()
        assert DEFAULT_DB_NAME not in db._engines
        assert DEFAULT_DB_NAME not in db._session_factories
        assert DEFAULT_DB_NAME not in db._setup_configs

    @pytest.mark.asyncio
    async def test_setup_same_name_with_different_config_raises(self):
        """Setup with different settings for the same database name should fail fast."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:")

        with pytest.raises(RuntimeError, match="already configured with different settings"):
            db.setup("sqlite+aiosqlite:///another.db")

        await db.shutdown()

    @pytest.mark.asyncio
    async def test_setup_same_sqlite_name_ignores_unused_pool_settings(self):
        """SQLite setup should stay idempotent when only ignored pool args differ."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:", pool_size=10, max_overflow=20)
        original_engine = db.engine

        db.setup("sqlite+aiosqlite:///:memory:", pool_size=99, max_overflow=199)

        assert db.engine is original_engine
        await db.shutdown()

    @pytest.mark.asyncio
    async def test_create_all(self):
        """Verify db.create_all() successfully creates tables."""
        if db._engines:
            await db.shutdown()

        # Define a model specifically for this test
        class TestCreateAllModel(SQLModel, table=True):
            __tablename__ = "test_create_all_table"
            id: int = Field(primary_key=True)
            name: str

        # Use in-memory SQLite for speed and isolation
        url = "sqlite+aiosqlite:///:memory:"
        db.setup(url)

        await db.create_all()

        async with db.session() as session:
            # Check if table exists in SQLite
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='test_create_all_table'")
            )
            table_name = result.scalar()
            assert table_name == "test_create_all_table"

        await db.shutdown()

    @pytest.mark.asyncio
    async def test_verify_connection(self):
        """Verify db.verify() successfully checks database connection."""
        if db._engines:
            await db.shutdown()

        url = "sqlite+aiosqlite:///:memory:"
        db.setup(url)
        try:
            result = await db.verify()
            assert result is True
        finally:
            await db.shutdown()


class TestSessionManagement:
    """Tests for session lifecycle handling and helper functions."""

    @pytest.mark.asyncio
    async def test_manage_session_success(self):
        """Verify manage_session handles normal execution flow."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        async with manage_session(mock_factory) as session:
            assert session == mock_session

        mock_session.close.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_manage_session_error(self):
        """Verify manage_session performs rollback on exception."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        with pytest.raises(ValueError, match="Database Error"):
            async with manage_session(mock_factory):
                raise ValueError("Database Error")

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.parametrize("name, url, connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_singleton_session_context(self, name, url, connect_args):
        """Verify the global db.session() works across different DBs."""
        if db._engines:
            await db.shutdown()

        db.setup(url, connect_args=connect_args)
        try:
            async with db.session() as session:
                assert isinstance(session, AsyncSession)
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
        finally:
            await db.shutdown()


class TestDependencyIntegration:
    """Tests for framework-specific dependency providers."""

    @pytest.mark.parametrize("name, url, connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_init_db_resource_lifecycle(self, name, url, connect_args):
        """Verify dependency_injector resource provider manages full lifecycle."""
        if db._engines:
            await db.shutdown()

        gen = init_db_resource(url, connect_args=connect_args)
        try:
            yielded_db = await anext(gen)
            assert yielded_db is db
            assert "default" in db._engines
        finally:
            await gen.aclose()
            # Explicit check after cleanup
            assert "default" not in db._engines

    @pytest.mark.asyncio
    async def test_init_db_resource_only_cleans_up_its_own_name(self):
        """Verify init_db_resource cleanup does not dispose other named databases."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:", name="other")
        gen = init_db_resource("sqlite+aiosqlite:///:memory:", name="default")
        try:
            yielded_db = await anext(gen)
            assert yielded_db is db
            assert "default" in db._engines
            assert "other" in db._engines
        finally:
            await gen.aclose()
            assert "default" not in db._engines
            assert "other" in db._engines
            await db.shutdown()

    @pytest.mark.parametrize("name, url, connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_get_session_fastapi_dependency(self, name, url, connect_args):
        """Verify the default dependency works across supported backends."""
        if db._engines:
            await db.shutdown()

        db.setup(url, connect_args=connect_args)
        gen = get_session()
        try:
            session = await anext(gen)
            assert isinstance(session, AsyncSession)
            await session.execute(text("SELECT 1"))
        finally:
            await gen.aclose()
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_named_session_dependencies_use_their_named_engines(self):
        """Named dependencies resolve only against their server-bound engines."""
        if db._engines:
            await db.shutdown()

        primary_dependency = session_dependency("primary")
        analytics_dependency = session_dependency("analytics")

        # Dependencies may be declared while routes are imported, before the
        # application lifespan configures its engines.
        db.setup("sqlite+aiosqlite:///:memory:", name="primary")
        db.setup("sqlite+aiosqlite:///:memory:", name="analytics")

        gen_p = primary_dependency()
        gen_a = analytics_dependency()
        try:
            session_p = await anext(gen_p)
            session_a = await anext(gen_a)
            assert isinstance(session_p, AsyncSession)
            assert isinstance(session_a, AsyncSession)
            assert session_p is not session_a
            assert session_p.bind is db.get_engine("primary")
            assert session_a.bind is db.get_engine("analytics")
        finally:
            await gen_p.aclose()
            await gen_a.aclose()
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_get_session_named_calls_remain_compatible(self):
        """The public get_session(name) API must keep selecting named engines."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:", name="primary")
        db.setup("sqlite+aiosqlite:///:memory:", name="analytics")

        primary_generator = get_session("primary")
        analytics_generator = get_session(name="analytics")
        try:
            primary_session = await anext(primary_generator)
            analytics_session = await anext(analytics_generator)
            assert primary_session.bind is db.get_engine("primary")
            assert analytics_session.bind is db.get_engine("analytics")
        finally:
            await primary_generator.aclose()
            await analytics_generator.aclose()
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_get_session_does_not_expose_database_name_to_fastapi(self):
        """Database selection must not become a client-controlled query parameter."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:")
        db.setup("sqlite+aiosqlite:///:memory:", name="analytics")
        app = FastAPI()

        @app.get("/items")
        async def list_items(session: Annotated[AsyncSession, Depends(get_session)]):
            return {"uses_default": session.bind is db.engine}

        try:
            operation = app.openapi()["paths"]["/items"]["get"]
            assert all(parameter["name"] != "name" for parameter in operation.get("parameters", []))

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/items", params={"name": "analytics"})

            assert response.status_code == 200
            assert response.json() == {"uses_default": True}
        finally:
            await db.shutdown()

    def test_session_dependency_signatures_preserve_the_public_api(self):
        """Introspection stays truthful without exposing a request selector."""
        analytics_session = session_dependency("analytics")

        assert not signature(analytics_session).parameters
        get_session_parameters = signature(get_session).parameters
        assert list(get_session_parameters) == ["name"]
        assert get_session_parameters["name"].default == DEFAULT_DB_NAME
        copied_default = deepcopy(get_session_parameters["name"].default)
        assert copied_default == DEFAULT_DB_NAME
        assert copied_default.dependency() == DEFAULT_DB_NAME
        assert "ServerControlledDatabaseName()" in repr(get_session_parameters["name"].annotation)
        assert "__signature__" not in vars(get_session)
        assert session_dependency(DEFAULT_DB_NAME) is get_session

        assert not signature(partial(get_session, "analytics")).parameters
        keyword_partial_parameters = signature(partial(get_session, name="analytics")).parameters
        assert keyword_partial_parameters["name"].default == "analytics"

        app = FastAPI()

        @app.get("/reports")
        async def list_reports(session: Annotated[AsyncSession, Depends(analytics_session)]):
            return {"ok": True}

        operation = app.openapi()["paths"]["/reports"]["get"]
        assert all(parameter["name"] != "name" for parameter in operation.get("parameters", []))

    def test_keyword_partial_get_session_fails_during_route_registration(self):
        """An unsupported keyword partial must never silently select default."""
        analytics_session = partial(get_session, name="analytics")
        app = FastAPI()

        with pytest.raises(FastAPIError, match=r"partial\(get_session, \.\.\.\).*session_dependency"):

            @app.get("/partial-reports")
            async def list_reports(session: Annotated[AsyncSession, Depends(analytics_session)]):
                return {"session": session}

    @pytest.mark.asyncio
    async def test_legacy_named_wrapper_remains_server_controlled(self):
        """The documented 0.7.0 wrapper stays compatible and request-safe."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:")
        db.setup("sqlite+aiosqlite:///:memory:", name="analytics")

        async def legacy_analytics_session():
            async for session in get_session("analytics"):
                yield session

        app = FastAPI()

        @app.get("/legacy-reports")
        async def list_reports(session: Annotated[AsyncSession, Depends(legacy_analytics_session)]):
            return {"uses_analytics": session.bind is db.get_engine("analytics")}

        try:
            operation = app.openapi()["paths"]["/legacy-reports"]["get"]
            assert all(parameter["name"] != "name" for parameter in operation.get("parameters", []))

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/legacy-reports", params={"name": "default"})

            assert response.status_code == 200
            assert response.json() == {"uses_analytics": True}
        finally:
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_named_session_dependency_supports_stored_callable_overrides(self):
        """Overrides target the same callable stored by route wiring."""
        analytics_session = session_dependency("analytics")
        override_session = MagicMock(spec=AsyncSession)

        async def override_analytics_session():
            yield override_session

        app = FastAPI()

        @app.get("/overridden-reports")
        async def list_reports(session: Annotated[AsyncSession, Depends(analytics_session)]):
            return {"overridden": session is override_session}

        app.dependency_overrides[analytics_session] = override_analytics_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/overridden-reports")

        assert response.status_code == 200
        assert response.json() == {"overridden": True}

    @pytest.mark.asyncio
    async def test_named_session_dependency_cleans_up_endpoint_errors(self, monkeypatch):
        """Endpoint exceptions pass through the dependency before response end."""
        events: list[str] = []

        @asynccontextmanager
        async def tracked_session(name=DEFAULT_DB_NAME):
            assert name == "analytics"
            events.append("open")
            try:
                yield MagicMock(spec=AsyncSession)
            except RuntimeError:
                events.append("rollback")
                raise
            finally:
                events.append("close")

        monkeypatch.setattr(db, "session", tracked_session)
        analytics_session = session_dependency("analytics")
        app = FastAPI()

        @app.get("/failing-reports")
        async def failing_reports(_session: Annotated[AsyncSession, Depends(analytics_session)]):
            raise RuntimeError("endpoint failed")

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/failing-reports")

        assert response.status_code == 500
        assert events == ["open", "rollback", "close"]

    @pytest.mark.asyncio
    async def test_named_session_dependency_uses_bound_database(self):
        """FastAPI must not override the database bound by a named dependency."""
        if db._engines:
            await db.shutdown()

        db.setup("sqlite+aiosqlite:///:memory:")
        db.setup("sqlite+aiosqlite:///:memory:", name="analytics")
        analytics_session = session_dependency("analytics")
        resolved_sessions: list[AsyncSession] = []
        app = FastAPI()

        @app.get("/reports")
        async def list_reports(
            session: Annotated[AsyncSession, Depends(analytics_session)],
            same_session: Annotated[AsyncSession, Depends(analytics_session)],
        ):
            resolved_sessions.append(session)
            return {
                "uses_analytics": session.bind is db.get_engine("analytics"),
                "reused_in_request": session is same_session,
            }

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                first = await client.get("/reports", params={"name": "default"})
                second = await client.get("/reports", params={"name": "default"})

            assert first.status_code == 200
            assert first.json() == {"uses_analytics": True, "reused_in_request": True}
            assert second.status_code == 200
            assert second.json() == {"uses_analytics": True, "reused_in_request": True}
            assert resolved_sessions[0] is not resolved_sessions[1]
        finally:
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_session_dependency_unknown_name_raises_on_resolution(self):
        """A named dependency looks up its engine only when it is resolved."""
        if db._engines:
            await db.shutdown()

        dependency = session_dependency("nonexistent")
        gen = dependency()
        with pytest.raises(RuntimeError, match="not initialized"):
            await anext(gen)
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_get_session_unknown_name_compatibility_raises_on_resolution(self):
        """The compatible named-call API keeps its unknown-database error."""
        if db._engines:
            await db.shutdown()

        gen = get_session("nonexistent")
        with pytest.raises(RuntimeError, match="not initialized"):
            await anext(gen)
        await gen.aclose()
