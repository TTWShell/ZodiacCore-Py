import pytest
from time import sleep
from datetime import timezone
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import text

from zodiac_core.db.sql import UUIDModel, IntIDModel

from .conftest import DB_URLS


class Product(UUIDModel, table=True):
    __tablename__ = "test_products"
    name: str
    price: float


class Category(IntIDModel, table=True):
    __tablename__ = "test_categories"
    name: str


class TestSQL:

    def _assert_uuid(self, session: Session, is_utc: bool = False):
        p1 = Product(name="MacBook Pro", price=2000.0)
        session.add(p1)
        session.commit()
        session.refresh(p1)

        assert p1.id is not None
        assert len(str(p1.id)) == 36

        assert p1.created_at is not None
        assert p1.updated_at is not None

        if is_utc:
            assert p1.created_at.tzinfo == timezone.utc

        original_created_at = p1.created_at
        original_updated_at = p1.updated_at

        sleep(1.1)
        p1.name = "MacBook Air"
        session.add(p1)
        session.commit()
        session.refresh(p1)

        # Created_at should NOT change
        assert p1.created_at == original_created_at
        # Updated_at SHOULD change (triggered by event listener)
        assert p1.updated_at > original_updated_at

    def _assert_id(self, engine, session: Session):
        c1 = Category(name="Electronics")
        session.add(c1)
        session.commit()
        session.refresh(c1)

        assert isinstance(c1.id, int)
        assert c1.id >= 1

        session.commit()
        # Raw insert into Category (id is auto-increment, only providing name)
        # created_at and updated_at should be filled by 'server_default'
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO test_categories (name) VALUES ('Books')"))
            conn.commit()

        c2 = session.exec(select(Category).where(Category.name == "Books")).one()
        assert c2.created_at is not None
        assert c2.updated_at is not None

    @pytest.mark.parametrize("name,url,connect_args", DB_URLS)
    def test_db_lifecycle(self, name, url, connect_args):
        """
        Test DB lifecycle across different engines:
        DDL -> Insert -> Verify Fields (ID/Time) -> Update -> Verify Time Change
        """
        extras = dict(connect_args=connect_args) if connect_args else {}
        engine = create_engine(url, **extras)

        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            self._assert_uuid(session, name == "postgresql")
            self._assert_id(engine, session)
