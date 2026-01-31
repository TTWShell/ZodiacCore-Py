from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.db.session import db

from .utils import DB_URLS


class TestBaseSQLRepository:
    """Tests for the BaseSQLRepository class."""

    @pytest.mark.parametrize("name, url, connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_repository_with_singleton_fallback(self, name, url, connect_args):
        """Test that repo uses global db singleton across different DBs."""
        if db._engines:
            await db.shutdown()

        db.setup(url, connect_args=connect_args)
        try:
            repo = BaseSQLRepository()
            async with repo.session() as session:
                assert isinstance(session, AsyncSession)
                # Ensure the session is bound to the correct engine
                await session.execute(text("SELECT 1"))
        finally:
            await db.shutdown()

    @pytest.mark.asyncio
    async def test_repository_with_custom_factory(self):
        """Test that repo uses injected factory and correctly handles its lifecycle."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        # Inject options as well to test __init__
        repo = BaseSQLRepository(session_factory=mock_factory, options={"debug": True})
        assert repo.options == {"debug": True}

        async with repo.session() as session:
            assert session == mock_session

        mock_factory.assert_called_once()
        mock_session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_custom_factory_error_handling(self):
        """Test that injected factory still triggers rollback on error via manage_session."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory = MagicMock(return_value=mock_session)

        repo = BaseSQLRepository(session_factory=mock_factory)

        with pytest.raises(RuntimeError, match="DB Fail"):
            async with repo.session():
                raise RuntimeError("DB Fail")

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
