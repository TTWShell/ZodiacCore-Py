import pytest
from datetime import timezone
from sqlmodel import SQLModel, Session, create_engine

from zodiac_core.db.sql import SQLBase, UUIDMixin
from zodiac_core.schemas import UUIDSchema

from .conftest import DB_URLS


# 1. DB Model
class ProductDB(SQLBase, UUIDMixin, table=True):
    __tablename__ = "schema_test_products"
    name: str
    price: float


# 2. Response Schema (DTO)
class ProductResponse(UUIDSchema):
    name: str
    price: float
    # UUIDSchema includes: CoreModel Config + UUID + CreatedAt + UpdatedAt


class TestSchemaConsistency:

    @pytest.mark.parametrize("name,url,connect_args", DB_URLS)
    def test_schema_serialization_consistency(self, name, url, connect_args):
        """
        Test that data retrieved from different DB engines is serialized
        consistently by Pydantic Schemas, especially Timezones.
        """
        extras = dict(connect_args=connect_args) if connect_args else {}
        engine = create_engine(url, **extras)

        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            p = ProductDB(name="Standard Item", price=99.9)
            session.add(p)
            session.commit()
            session.refresh(p)

            dto = ProductResponse.model_validate(p)

            assert dto.name == "Standard Item"
            assert str(dto.id) == str(p.id)

            assert dto.created_at.tzinfo is not None, f"{name}: created_at lost timezone info"
            assert dto.created_at.tzinfo == timezone.utc, f"{name}: created_at is not UTC"

            assert dto.updated_at.tzinfo is not None
            assert dto.updated_at.tzinfo == timezone.utc

            json_output = dto.model_dump_json()

            import json
            data = json.loads(json_output)

            created_str = data["created_at"]
            assert created_str.endswith("+00:00") or created_str.endswith("Z"), \
                f"{name}: JSON output {created_str} does not look like UTC ISO format"
