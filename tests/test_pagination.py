from typing import Annotated

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from zodiac_core.pagination import PagedResponse, PageParams, PageSortParams, SortParams, SortSpec


class UserDTO(BaseModel):
    id: int
    name: str


class TestPageParams:
    """Tests for the PageParams model validation and defaults."""

    def test_defaults(self):
        p = PageParams()
        assert p.page == 1
        assert p.size == 20

    def test_valid_custom_values(self):
        p = PageParams(page=2, size=50)
        assert p.page == 2
        assert p.size == 50

    def test_invalid_page(self):
        with pytest.raises(ValidationError):
            PageParams(page=0)

    def test_invalid_size_min(self):
        with pytest.raises(ValidationError):
            PageParams(size=0)

    def test_invalid_size_max(self):
        with pytest.raises(ValidationError):
            PageParams(size=101)


class TestSortParams:
    """Tests for standard multi-column sort query parameters."""

    def test_defaults(self):
        p = SortParams()
        assert p.sort == []

    def test_parse_sort_expressions(self):
        p = SortParams(sort=["name:asc", "created_at:desc"])
        assert p.sort == ["name:asc", "created_at:desc"]
        assert p.sort_pairs == [("name", "asc"), ("created_at", "desc")]

    def test_default_direction(self):
        p = SortParams(sort=["name"])
        assert p.sort == ["name"]
        assert p.sort_pairs == [("name", "asc")]

    def test_invalid_direction(self):
        with pytest.raises(ValidationError):
            SortParams(sort=["name:invalid"])

    def test_empty_field(self):
        with pytest.raises(ValidationError):
            SortParams(sort=[":asc"])


class TestSortSpec:
    """Tests for reusable sort configuration."""

    def test_default_pairs_from_strings_and_tuples(self):
        spec = SortSpec(
            columns={"name": object(), "created_at": object()},
            default=["created_at:desc", ("name", "asc")],
        )

        assert spec.default_pairs == [("created_at", "desc"), ("name", "asc")]
        assert spec.pairs_for(SortParams()) == [("created_at", "desc"), ("name", "asc")]

    def test_request_sort_overrides_default(self):
        spec = SortSpec(
            columns={"name": object(), "created_at": object()},
            default=["created_at:desc"],
        )

        assert spec.pairs_for(SortParams(sort=["name:asc"])) == [("name", "asc")]

    def test_rejects_default_field_not_in_columns(self):
        with pytest.raises(ValueError, match="created_at"):
            SortSpec(columns={"name": object()}, default=["created_at:desc"])


class TestPagedResponse:
    """Tests for the PagedResponse model and its factory method."""

    def test_create_factory(self):
        items = [UserDTO(id=1, name="Alice"), UserDTO(id=2, name="Bob")]
        total = 105
        params = PageParams(page=1, size=10)

        resp = PagedResponse[UserDTO].create(items, total, params)

        assert resp.items == items
        assert resp.total == 105
        assert resp.page == 1
        assert resp.size == 10


class TestPaginationIntegration:
    """Integration tests with FastAPI to verify Query model mapping."""

    @pytest.fixture
    def client(self):
        app = FastAPI()

        @app.get("/users", response_model=PagedResponse[UserDTO])
        def list_users(page_params: Annotated[PageParams, Query()]):
            all_users = [UserDTO(id=i, name=f"User {i}") for i in range(1, 101)]
            start = (page_params.page - 1) * page_params.size
            end = start + page_params.size
            items = all_users[start:end]
            return PagedResponse.create(items, len(all_users), page_params)

        @app.get("/sorted-users")
        def list_sorted_users(params: Annotated[PageSortParams, Query()]):
            return params.model_dump()

        return TestClient(app)

    def test_default_pagination(self, client):
        response = client.get("/users")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 20
        assert len(data["items"]) == 20

    def test_custom_pagination(self, client):
        response = client.get("/users?page=3&size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 3
        assert data["size"] == 10
        assert data["items"][0]["id"] == 21  # (3-1)*10 + 1

    def test_validation_error(self, client):
        response = client.get("/users?size=200")
        assert response.status_code == 422
        assert "less than or equal to 100" in response.text

    def test_sort_query_params(self, client):
        response = client.get("/sorted-users?page=2&size=5&sort=name:asc&sort=created_at:desc")
        assert response.status_code == 200
        assert response.json() == {
            "sort": ["name:asc", "created_at:desc"],
            "page": 2,
            "size": 5,
        }

    def test_sort_openapi_schema_uses_string_wire_format(self, client):
        schema = client.get("/openapi.json").json()
        params = schema["paths"]["/sorted-users"]["get"]["parameters"]
        sort_param = next(param for param in params if param["name"] == "sort")

        assert sort_param["schema"]["type"] == "array"
        assert sort_param["schema"]["items"]["type"] == "string"
