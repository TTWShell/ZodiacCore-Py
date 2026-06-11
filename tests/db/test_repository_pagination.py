import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlmodel import Field, SQLModel

from zodiac_core.db.repository import BaseSQLRepository
from zodiac_core.db.session import db
from zodiac_core.exceptions import BadRequestException
from zodiac_core.pagination import PageParams, PageSortParams, SortParams


# 1. Define Test Models
class ItemModel(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str


class SortableItemModel(SQLModel, table=True):
    __tablename__ = "test_sortable_item"

    id: int = Field(default=None, primary_key=True)
    name: str
    priority: int


class ItemModelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# 2. Setup Test Repository
class ItemModelRepository(BaseSQLRepository):
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
                session.add(ItemModel(name=f"Item {i:02d}"))
            session.add(SortableItemModel(name="banana", priority=1))
            session.add(SortableItemModel(name="apple", priority=1))
            session.add(SortableItemModel(name="apple", priority=2))
            session.add(SortableItemModel(name="banana", priority=2))
            await session.commit()

        yield
        await db.shutdown()

    @pytest.mark.asyncio
    async def test_paginate_first_page(self):
        """Test fetching the first page (default size 20)."""
        repo = ItemModelRepository()
        params = PageParams(page=1, size=10)

        async with repo.session() as session:
            stmt = select(ItemModel).order_by(ItemModel.id)
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
        repo = ItemModelRepository()
        params = PageParams(page=3, size=10)

        async with repo.session() as session:
            stmt = select(ItemModel).order_by(ItemModel.id)
            result = await repo.paginate(session, stmt, params)

            assert result.total == 25
            assert len(result.items) == 5
            assert result.items[0].name == "Item 21"
            assert result.items[-1].name == "Item 25"

    @pytest.mark.asyncio
    async def test_paginate_with_transformer(self):
        """Test that transformer correctly converts DB models to schemas."""
        repo = ItemModelRepository()
        params = PageParams(page=1, size=5)

        async with repo.session() as session:
            stmt = select(ItemModel)
            result = await repo.paginate(session, stmt, params, transformer=ItemModelSchema)

            assert len(result.items) == 5
            assert isinstance(result.items[0], ItemModelSchema)
            assert not isinstance(result.items[0], ItemModel)
            assert result.items[0].name == "Item 01"

    @pytest.mark.asyncio
    async def test_paginate_query_convenience(self):
        """Test the paginate_query convenience method (auto session)."""
        repo = ItemModelRepository()
        params = PageParams(page=2, size=10)

        stmt = select(ItemModel).order_by(ItemModel.id)
        result = await repo.paginate_query(stmt, params)

        assert result.total == 25
        assert len(result.items) == 10
        assert result.items[0].name == "Item 11"

    @pytest.mark.asyncio
    async def test_paginate_query_applies_sorting(self):
        """Test paginating with standard multi-column sort params."""
        repo = ItemModelRepository()
        params = PageSortParams(page=1, size=10, sort=["name:asc", "priority:desc"])

        result = await repo.paginate_query(
            select(SortableItemModel).order_by(SortableItemModel.id),
            params,
            sort_columns={
                "name": SortableItemModel.name,
                "priority": SortableItemModel.priority,
            },
        )

        assert result.total == 4
        assert [(item.name, item.priority) for item in result.items] == [
            ("apple", 2),
            ("apple", 1),
            ("banana", 2),
            ("banana", 1),
        ]

    @pytest.mark.asyncio
    async def test_paginate_query_requires_sort_params_for_sort_columns(self):
        repo = ItemModelRepository()

        with pytest.raises(TypeError):
            await repo.paginate_query(
                select(SortableItemModel),
                PageParams(),
                sort_columns={"name": SortableItemModel.name},
            )

    @pytest.mark.asyncio
    async def test_paginate_empty_result(self):
        """Test pagination on a query that returns no results."""
        repo = ItemModelRepository()
        params = PageParams(page=1, size=10)

        stmt = select(ItemModel).where(ItemModel.name == "Non-existent")
        result = await repo.paginate_query(stmt, params)

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_apply_sorting(self):
        """Test applying public multi-column sort fields to a statement."""
        repo = ItemModelRepository()
        params = SortParams(sort=["name:asc", "priority:desc"])

        stmt = repo.apply_sorting(
            select(SortableItemModel),
            params,
            {
                "name": SortableItemModel.name,
                "priority": SortableItemModel.priority,
            },
        )

        async with repo.session() as session:
            result = await session.execute(stmt)
            items = result.scalars().all()

        assert [(item.name, item.priority) for item in items] == [
            ("apple", 2),
            ("apple", 1),
            ("banana", 2),
            ("banana", 1),
        ]

    @pytest.mark.asyncio
    async def test_apply_sorting_replaces_existing_order_by(self):
        repo = ItemModelRepository()
        params = SortParams(sort=["name:asc", "priority:desc"])

        stmt = repo.apply_sorting(
            select(SortableItemModel).order_by(SortableItemModel.id),
            params,
            {
                "name": SortableItemModel.name,
                "priority": SortableItemModel.priority,
            },
        )

        async with repo.session() as session:
            result = await session.execute(stmt)
            items = result.scalars().all()

        assert [(item.name, item.priority) for item in items] == [
            ("apple", 2),
            ("apple", 1),
            ("banana", 2),
            ("banana", 1),
        ]

    def test_apply_sorting_rejects_unknown_field(self):
        repo = ItemModelRepository()
        params = SortParams(sort=["unknown:asc"])

        with pytest.raises(BadRequestException):
            repo.apply_sorting(select(SortableItemModel), params, {"name": SortableItemModel.name})
