import json
from collections.abc import AsyncIterable, Iterator
from functools import partial, wraps
from typing import Annotated, Union

import pytest
from fastapi import APIRouter as NativeAPIRouter
from fastapi import FastAPI
from fastapi import Response as FastAPIResponse
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from zodiac_core import APIRouter as ZodiacAPIRouter
from zodiac_core import Response, response_ok
from zodiac_core.routing import _SUPPORTS_YIELD_STREAMING, ZodiacRoute

try:
    from fastapi.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None


class User(BaseModel):
    """Mock user data model."""

    id: int
    name: str


class ErrorMessage(BaseModel):
    """Mock error response model."""

    detail: str


def get_router_route(router: ZodiacAPIRouter, path: str):
    """Return a route registered directly on a Zodiac router."""
    return next(route for route in router.routes if getattr(route, "path", None) == path)


class TestZodiacRouting:
    """Tests for Zodiac routing enhancements, including response wrapping and OpenAPI doc generation."""

    @pytest.fixture(scope="class")
    def routing_app(self):
        app = FastAPI(title="Zodiac Test App")

        # 1. Native route: comparison group
        native_router = NativeAPIRouter(prefix="/native")

        @native_router.get("/user", response_model=User)
        async def get_native_user():
            return User(id=1, name="Native")

        # 2. Zodiac route: verify automatic wrapping logic
        zodiac_router = ZodiacAPIRouter(prefix="/zodiac")

        @zodiac_router.get("/user", response_model=User)
        async def get_zodiac_user():
            return User(id=2, name="Zodiac")

        # 3. Mixed scenario: manually return Response object to verify prevention of double wrapping
        @zodiac_router.get("/manual")
        async def get_manual_response():
            return response_ok(data={"item": "manual"})

        # 4. Conflict scenario: verify 409 and multiple response wrapping
        @zodiac_router.post(
            "/conflict",
            response_model=User,
            responses={409: {"model": ErrorMessage, "description": "Conflict"}},
        )
        async def create_user_conflict():
            return Response(code=409, message="User already exists", data=None)

        app.include_router(native_router)
        app.include_router(zodiac_router)
        return app

    @pytest.fixture(scope="class")
    def client(self, routing_app):
        return TestClient(routing_app)

    def test_response_structure_comparison(self, client):
        """Scenario 1: Ensure response contains the three core elements and compare with native behavior."""

        # Verify native: should return model JSON directly
        native_resp = client.get("/native/user")
        assert native_resp.status_code == 200
        native_data = native_resp.json()
        assert "id" in native_data
        assert "code" not in native_data

        # Verify Zodiac: should include code, data, and message
        zodiac_resp = client.get("/zodiac/user")
        assert zodiac_resp.status_code == 200
        zodiac_body = zodiac_resp.json()

        assert "code" in zodiac_body
        assert "data" in zodiac_body
        assert "message" in zodiac_body
        assert zodiac_body["code"] == 0
        assert zodiac_body["message"] == "Success"
        assert zodiac_body["data"]["id"] == 2
        assert zodiac_body["data"]["name"] == "Zodiac"

    def test_no_double_wrapping(self, client):
        """Scenario 2: Ensure manual Response return doesn't result in double wrapping."""
        resp = client.get("/zodiac/manual")
        body = resp.json()

        assert body["code"] == 0
        assert body["data"] == {"item": "manual"}
        assert isinstance(body["data"], dict)
        assert "item" in body["data"]

    def test_conflict_response(self, client):
        """Scenario 3: Ensure 409 conflict scenario returns correct business code and structure."""
        resp = client.post("/zodiac/conflict")
        body = resp.json()
        assert body["code"] == 409
        assert body["message"] == "User already exists"
        assert body["data"] is None

    def test_openapi_schema_contract(self, routing_app):
        """Scenario 4: Ensure OpenAPI (Swagger) documentation definitions are correct."""
        schema = routing_app.openapi()

        # 1. Verify native interface doc: points to User model
        native_path = schema["paths"]["/native/user"]["get"]["responses"]["200"]
        native_schema_ref = native_path["content"]["application/json"]["schema"]["$ref"]
        assert "User" in native_schema_ref

        # 2. Verify Zodiac interface doc: points to Response[User] (Pydantic native generics)
        zodiac_path = schema["paths"]["/zodiac/user"]["get"]["responses"]["200"]
        zodiac_schema_ref = zodiac_path["content"]["application/json"]["schema"]["$ref"]
        # Pydantic generates names like "Response_User_" for Response[User]
        assert "Response" in zodiac_schema_ref and "User" in zodiac_schema_ref

        # 3. Verify wrapped model structure exists in components
        components = schema["components"]["schemas"]
        # Find the Response[User] model (Pydantic may name it Response_User_ or similar)
        response_user_models = [k for k in components if "Response" in k and "User" in k]
        assert len(response_user_models) >= 1, f"Expected Response[User] model, got: {list(components.keys())}"

        wrapped_model = components[response_user_models[0]]
        props = wrapped_model["properties"]
        assert "code" in props
        assert "message" in props
        assert "data" in props

        # Verify data field reference logic (handling anyOf for nullable fields in OpenAPI 3.1+)
        data_schema = props["data"]
        if "$ref" in data_schema:
            assert "User" in data_schema["$ref"]
        elif "anyOf" in data_schema:
            assert any("User" in item.get("$ref", "") for item in data_schema["anyOf"])

        # 4. Verify 409 error response is also wrapped
        conflict_responses = schema["paths"]["/zodiac/conflict"]["post"]["responses"]
        assert "409" in conflict_responses
        conflict_ref = conflict_responses["409"]["content"]["application/json"]["schema"]["$ref"]
        assert "Response" in conflict_ref and "ErrorMessage" in conflict_ref


class TestFastAPIRouterCompatibility:
    """Verify Zodiac routing preserves FastAPI response model semantics."""

    def test_omitted_response_model_without_annotation_uses_any_envelope(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/untyped")
        async def get_untyped_user():
            return {"id": 1, "name": "Untyped", "internal": "kept"}

        app.include_router(router)
        response = TestClient(app).get("/untyped")

        assert response.json() == {
            "code": 0,
            "data": {"id": 1, "name": "Untyped", "internal": "kept"},
            "message": "Success",
        }
        response_ref = app.openapi()["paths"]["/untyped"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        assert "Response_Any_" in response_ref

    def test_omitted_response_model_uses_return_annotation(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/typed")
        async def get_typed_user() -> User:
            return {"id": 1, "name": "Typed", "internal": "filtered"}

        app.include_router(router)
        response = TestClient(app).get("/typed")

        assert response.json() == {
            "code": 0,
            "data": {"id": 1, "name": "Typed"},
            "message": "Success",
        }
        response_ref = app.openapi()["paths"]["/typed"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        assert "Response" in response_ref and "User" in response_ref

    def test_explicit_none_keeps_untyped_automatic_envelope(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/unwrapped", response_model=None)
        async def get_unwrapped_user() -> User:
            return {"id": 1, "name": "Unwrapped", "internal": "kept"}

        app.include_router(router)
        response = TestClient(app).get("/unwrapped")

        assert response.json() == {
            "code": 0,
            "data": {"id": 1, "name": "Unwrapped", "internal": "kept"},
            "message": "Success",
        }
        response_ref = app.openapi()["paths"]["/unwrapped"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        assert "Response_Any_" in response_ref

    def test_fastapi_response_return_annotation_disables_envelope_model(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/raw")
        async def get_raw_response() -> FastAPIResponse:
            return FastAPIResponse("raw", media_type="text/plain")

        app.include_router(router)
        response = TestClient(app).get("/raw")

        assert get_router_route(router, "/raw").response_model is None
        assert response.status_code == 200
        assert response.content == b"raw"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        response_schema = app.openapi()["paths"]["/raw"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert response_schema == {}

    def test_explicit_none_preserves_annotated_fastapi_response_passthrough(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/raw", response_model=None)
        async def get_raw_response() -> FastAPIResponse:
            return FastAPIResponse("raw", media_type="text/plain")

        app.include_router(router)
        response = TestClient(app).get("/raw")

        assert get_router_route(router, "/raw").response_model is None
        assert response.content == b"raw"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

    @pytest.mark.parametrize(
        "route_options",
        [{}, {"response_model": None}],
        ids=["omitted", "explicit-none"],
    )
    def test_typing_annotated_fastapi_response_disables_envelope_model(self, route_options):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/raw", **route_options)
        async def get_raw_response() -> Annotated[FastAPIResponse, "raw"]:
            return FastAPIResponse("raw", media_type="text/plain")

        app.include_router(router)
        response = TestClient(app).get("/raw")

        assert get_router_route(router, "/raw").response_model is None
        assert response.content == b"raw"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        response_schema = app.openapi()["paths"]["/raw"]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert response_schema == {}

    def test_annotated_zodiac_response_model_is_not_double_wrapped(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/wrapped", response_model=Annotated[Response[User], "metadata"])
        async def get_wrapped_user():
            return Response(data=User(id=1, name="Wrapped"))

        app.include_router(router)
        response = TestClient(app).get("/wrapped")

        assert response.json() == {
            "code": 0,
            "data": {"id": 1, "name": "Wrapped"},
            "message": "Success",
        }

    @pytest.mark.parametrize("status_code", [199, 204, 205, 304])
    def test_bodyless_status_code_skips_envelope(self, status_code):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get(f"/{status_code}", status_code=status_code)
        async def get_bodyless_response():
            return FastAPIResponse(status_code=status_code)

        app.include_router(router)

        assert get_router_route(router, f"/{status_code}").response_model is None
        documented_response = app.openapi()["paths"][f"/{status_code}"]["get"]["responses"][str(status_code)]
        assert "content" not in documented_response

        if status_code != 199:
            response = TestClient(app).get(f"/{status_code}")
            assert response.status_code == status_code
            assert response.content == b""

    def test_explicit_none_allows_bodyless_status_code(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.delete("/resource", status_code=204, response_model=None)
        async def delete_resource():
            return FastAPIResponse(status_code=204)

        app.include_router(router)
        response = TestClient(app).delete("/resource")

        assert get_router_route(router, "/resource").response_model is None
        assert response.status_code == 204
        assert response.content == b""

    def test_additional_bodyless_response_allows_none_model(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/resource", responses={204: {"model": None, "description": "No content"}})
        async def get_resource():
            return {"id": 1, "name": "Resource"}

        app.include_router(router)
        documented_response = app.openapi()["paths"]["/resource"]["get"]["responses"]["204"]

        assert documented_response == {"description": "No content"}

    def test_bodyless_status_code_rejects_explicit_response_model(self):
        router = ZodiacAPIRouter()

        with pytest.raises(AssertionError, match="Status code 204 must not have a response body"):

            @router.delete("/resource", status_code=204, response_model=User)
            async def delete_resource():
                return FastAPIResponse(status_code=204)

    def test_bodyless_status_code_rejects_inferred_response_model(self):
        router = ZodiacAPIRouter()

        with pytest.raises(AssertionError, match="Status code 204 must not have a response body"):

            @router.delete("/resource", status_code=204)
            async def delete_resource() -> User:
                return User(id=1, name="Unexpected")

    @pytest.mark.skipif(_SUPPORTS_YIELD_STREAMING, reason="requires FastAPI without yield streaming support")
    def test_legacy_generator_keeps_automatic_envelope(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/users")
        def stream_users():
            yield {"id": 1, "name": "First"}
            yield {"id": 2, "name": "Second"}

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.json() == {
            "code": 0,
            "data": [
                {"id": 1, "name": "First"},
                {"id": 2, "name": "Second"},
            ],
            "message": "Success",
        }


@pytest.mark.skipif(not _SUPPORTS_YIELD_STREAMING, reason="installed FastAPI has no yield streaming support")
class TestFastAPIStreamingCompatibility:
    """Verify stream endpoints retain FastAPI's native generator semantics."""

    def test_sync_binary_generator_streams_without_response_model_override(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/binary", response_class=StreamingResponse)
        def stream_binary() -> Iterator[bytes]:
            yield b"a"
            yield b"b"

        app.include_router(router)
        response = TestClient(app).get("/binary")

        assert get_router_route(router, "/binary").response_model is None
        assert response.status_code == 200
        assert response.content == b"ab"

    def test_async_binary_generator_streams_with_explicit_none_response_model(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/binary", response_class=StreamingResponse, response_model=None)
        async def stream_binary() -> AsyncIterable[bytes]:
            yield b"a"
            yield b"b"

        app.include_router(router)
        response = TestClient(app).get("/binary")

        assert get_router_route(router, "/binary").response_model is None
        assert response.status_code == 200
        assert response.content == b"ab"

    def test_sync_generator_uses_fastapi_jsonl_streaming(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/users")
        def stream_users() -> Iterator[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_async_generator_uses_fastapi_jsonl_streaming(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/users")
        async def stream_users() -> AsyncIterable[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_sync_callable_object_uses_fastapi_jsonl_streaming(self):
        class StreamUsers:
            def __call__(self) -> Iterator[User]:
                yield User(id=1, name="First")
                yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", StreamUsers(), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_async_callable_object_uses_fastapi_jsonl_streaming(self):
        class StreamUsers:
            async def __call__(self) -> AsyncIterable[User]:
                yield User(id=1, name="First")
                yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", StreamUsers(), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_partial_sync_callable_object_uses_fastapi_jsonl_streaming(self):
        class StreamUsers:
            def __call__(self) -> Iterator[User]:
                yield User(id=1, name="First")
                yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", partial(partial(StreamUsers())), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_partial_async_callable_object_uses_fastapi_jsonl_streaming(self):
        class StreamUsers:
            async def __call__(self) -> AsyncIterable[User]:
                yield User(id=1, name="First")
                yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", partial(partial(StreamUsers())), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_partial_decorated_generator_uses_fastapi_jsonl_streaming(self):
        def decorator(endpoint):
            @wraps(endpoint)
            def wrapper(*args, **kwargs):
                return endpoint(*args, **kwargs)

            return wrapper

        @decorator
        def stream_users() -> Iterator[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", partial(stream_users), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    def test_generator_with_non_generator_wrapped_metadata_uses_fastapi_jsonl_streaming(self):
        def metadata_source() -> Iterator[User]:
            return iter(())

        @wraps(metadata_source)
        def stream_users() -> Iterator[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app = FastAPI()
        router = ZodiacAPIRouter()
        router.add_api_route("/users", partial(stream_users), methods=["GET"])

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("application/jsonl")
        assert [json.loads(line) for line in response.content.splitlines()] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    @pytest.mark.skipif(EventSourceResponse is None, reason="installed FastAPI has no SSE support")
    def test_sync_generator_uses_fastapi_sse_streaming(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/users", response_class=EventSourceResponse)
        def stream_users() -> Iterator[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("text/event-stream")
        assert [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]

    @pytest.mark.skipif(EventSourceResponse is None, reason="installed FastAPI has no SSE support")
    def test_async_generator_uses_fastapi_sse_streaming(self):
        app = FastAPI()
        router = ZodiacAPIRouter()

        @router.get("/users", response_class=EventSourceResponse)
        async def stream_users() -> AsyncIterable[User]:
            yield User(id=1, name="First")
            yield User(id=2, name="Second")

        app.include_router(router)
        response = TestClient(app).get("/users")

        assert response.headers["content-type"].startswith("text/event-stream")
        assert [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line] == [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
        ]


class TestRoutingInternalLogic:
    """Unit tests for internal routing logic to ensure 100% code coverage."""

    def test_should_wrap_logic(self):
        """Response envelopes, including Annotated models, are not wrapped twice."""

        class MyResponse(Response):
            pass

        # 1. Standard types
        assert ZodiacRoute._should_wrap(User) is True
        assert ZodiacRoute._should_wrap(None) is False

        # 2. Response subclasses
        assert ZodiacRoute._should_wrap(Response) is False
        assert ZodiacRoute._should_wrap(MyResponse) is False

        # 3. Generic and Annotated response envelopes
        assert ZodiacRoute._should_wrap(Response[User]) is False
        assert ZodiacRoute._should_wrap(Annotated[Response[User], "metadata"]) is False

        # 4. Union types
        assert ZodiacRoute._should_wrap(Union[User, None]) is True

        # Callable classes are not generator endpoints until instantiated.
        assert ZodiacRoute._is_generator_callable(User) is False
