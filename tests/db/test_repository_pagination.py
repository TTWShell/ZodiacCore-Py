import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlmodel import Field, SQLModel

from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.db.session import db
from zodiac_core.pagination import PageParams


# 1. Define Test Models
class TestItem(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str

class TestItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str

# 2. Setup Test Repository
class TestItemRepository(BaseSQLRepository):
    def __init__(self):
        super().__init__()

# 3. Pagination Test Class
class TestRepositoryPagination:

    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self):
        """Setup in-memory SQLite for each test."""
        db.setup("sqlite+aiosqlite:///:memory:")
        await db.create_all()

        # Seed Data: 25 items
        async with db.session() as session:
            for i in range(1, 26):
                session.add(TestItem(name=f"Item {i:02d}"))
            await session.commit()

        yield
        await db.shutdown()

    @pytest.mark.asyncio
    async def test_paginate_first_page(self):
        """Test fetching the first page (default size 20)."""
        repo = TestItemRepository()
        params = PageParams(page=1, size=10)

        async with repo.session() as session:
            stmt = select(TestItem).order_by(TestItem.id)
            result = await repo.paginate(session, stmt, params)

            assert result.total == 25
            assert len(result.items) == 10
            assert result.page == 1
            assert result.size == 10
            assert result.items[0].name == "Item 01"
            assert result.items[-1].name == "Item 10"

    @pytest.mark.asyncio
    async def test_paginate_last_page(self):
        """Test fetching the last page (remaining items)."""
        repo = TestItemRepository()
        params = PageParams(page=3, size=10)

        async with repo.session() as session:
            stmt = select(TestItem).order_by(TestItem.id)
            result = await repo.paginate(session, stmt, params)

            assert result.total == 25
            assert len(result.items) == 5
            assert result.items[0].name == "Item 21"
            assert result.items[-1].name == "Item 25"

    @pytest.mark.asyncio
    async def test_paginate_with_transformer(self):
        """Test that transformer correctly converts DB models to schemas."""
        repo = TestItemRepository()
        params = PageParams(page=1, size=5)

        async with repo.session() as session:
            stmt = select(TestItem)
            result = await repo.paginate(session, stmt, params, transformer=TestItemSchema)

            assert len(result.items) == 5
            assert isinstance(result.items[0], TestItemSchema)
            assert not isinstance(result.items[0], TestItem)
            assert result.items[0].name == "Item 01"

    @pytest.mark.asyncio
    async def test_paginate_query_convenience(self):
        """Test the paginate_query convenience method (auto session)."""
        repo = TestItemRepository()
        params = PageParams(page=2, size=10)

        stmt = select(TestItem).order_by(TestItem.id)
        result = await repo.paginate_query(stmt, params)

        assert result.total == 25
        assert len(result.items) == 10
        assert result.items[0].name == "Item 11"

    @pytest.mark.asyncio
    async def test_paginate_empty_result(self):
        """Test pagination on a query that returns no results."""
        repo = TestItemRepository()
        params = PageParams(page=1, size=10)

        stmt = select(TestItem).where(TestItem.name == "Non-existent")
        result = await repo.paginate_query(stmt, params)

        assert result.total == 0
        assert len(result.items) == 0
