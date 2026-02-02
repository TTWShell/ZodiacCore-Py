import uuid

import pytest

from zodiac_core.db.sql import IntIDModel, UUIDModel

from .utils import DB_URLS, managed_db_session


# Define concrete models inheriting from our mixins
class ConcreteIntUser(IntIDModel, table=True):
    __tablename__ = "test_concrete_int_user"
    name: str


class ConcreteUUIDUser(UUIDModel, table=True):
    __tablename__ = "test_concrete_uuid_user"
    name: str


class TestModelMixins:
    """
    Test the usability of provided SQLModel mixins.
    Ensures they can be instantiated without providing primary keys (auto-generation).
    """

    def test_int_id_model_instantiation(self):
        """
        Verify that IntIDModel allows instantiation without an ID.
        This confirms that id field has a default value (None) allowing DB auto-increment.
        """
        user = ConcreteIntUser(name="Alice")
        assert user.id is None
        assert user.name == "Alice"
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_uuid_model_instantiation(self):
        """Verify that UUIDModel automatically generates a UUID on instantiation."""
        user = ConcreteUUIDUser(name="Bob")
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.name == "Bob"


@pytest.mark.serial
class TestModelPersistence:
    """
    Test the persistence layer for SQLModel mixins.
    Ensures DB-side generation (auto-increment, server_defaults) works as expected.
    """

    @pytest.mark.parametrize("name,url,connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_orm_auto_increment_and_timestamps(self, name, url, connect_args):
        """Verify that mixins work correctly with the ORM lifecycle (id=None fix)."""
        async with managed_db_session(url, connect_args) as (_, session):
            user = ConcreteIntUser(name="ORM User")
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert user.id > 0
            assert user.created_at is not None
            assert user.updated_at is not None

    @pytest.mark.parametrize("name,url,connect_args", DB_URLS)
    @pytest.mark.asyncio
    async def test_raw_sql_server_defaults(self, name, url, connect_args):
        """Verify that server-side defaults work when bypassing the ORM (DDL check)."""
        from sqlalchemy import text
        from sqlmodel import select

        async with managed_db_session(url, connect_args) as (_, session):
            await session.execute(text("INSERT INTO test_concrete_int_user (name) VALUES ('Raw SQL User')"))
            await session.commit()

            result = await session.execute(select(ConcreteIntUser).where(ConcreteIntUser.name == "Raw SQL User"))
            user = result.scalar_one()

            assert user.id is not None
            assert user.created_at is not None
            assert user.updated_at is not None
