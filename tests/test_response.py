import json

from fastapi import status

from zodiac_core.response import (
    create_response,
    response_created,
    response_ok,
)


class TestResponseHelpers:
    """Test response_ok, response_created, and create_response."""

    def test_response_ok_default(self):
        """Test response_ok returns 200 with default code 0 and Success message."""
        resp = response_ok()
        assert resp.status_code == status.HTTP_200_OK
        data = json.loads(resp.body)
        assert data["code"] == 0
        assert data["message"] == "Success"
        assert data["data"] is None

    def test_response_ok_with_data(self):
        """Test response_ok with custom data and message."""
        resp = response_ok(data={"id": 1}, message="OK")
        assert resp.status_code == status.HTTP_200_OK
        data = json.loads(resp.body)
        assert data["data"] == {"id": 1}
        assert data["message"] == "OK"

    def test_response_created_default(self):
        """Test response_created returns 201 with default message."""
        resp = response_created()
        assert resp.status_code == status.HTTP_201_CREATED
        data = json.loads(resp.body)
        assert data["code"] == status.HTTP_201_CREATED
        assert data["message"] == "Created"
        assert data["data"] is None

    def test_response_created_with_data(self):
        """Test response_created with custom data and message."""
        resp = response_created(data={"id": 42}, message="Resource created")
        assert resp.status_code == status.HTTP_201_CREATED
        data = json.loads(resp.body)
        assert data["data"] == {"id": 42}
        assert data["message"] == "Resource created"

    def test_create_response_explicit_code(self):
        """Test create_response with explicit business code."""
        resp = create_response(
            http_code=status.HTTP_200_OK,
            code=1000,
            data=None,
            message="Custom",
        )
        assert resp.status_code == 200
        data = json.loads(resp.body)
        assert data["code"] == 1000
        assert data["message"] == "Custom"
