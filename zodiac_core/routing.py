import inspect
from functools import wraps
from typing import Annotated, Any, Callable, Dict, Optional, Union, get_args, get_origin

from fastapi import APIRouter as FastAPIRouter
from fastapi import Response as FastAPIResponse
from fastapi._compat import lenient_issubclass
from fastapi.datastructures import Default, DefaultPlaceholder  # FastAPI internal, requires >=0.128.0
from fastapi.dependencies.utils import get_typed_return_annotation
from fastapi.routing import APIRoute
from fastapi.utils import is_body_allowed_for_status_code

from zodiac_core.response import Response

_DEFAULT_RESPONSE_MODEL = Default(None)


def _unwrap_annotated(annotation: Any) -> Any:
    """Return the underlying type while ignoring Annotated metadata."""
    while get_origin(annotation) is Annotated:
        annotation, *_ = get_args(annotation)
    return annotation


class ZodiacRoute(APIRoute):
    """
    Custom APIRoute that wraps body-bearing response models and endpoint returns
    with the standard Response[T] structure by default.

    Raw Response objects pass through at runtime, while status codes that
    prohibit a response body bypass automatic wrapping entirely.
    """

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        response_model: Any = _DEFAULT_RESPONSE_MODEL,
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        **kwargs,
    ) -> None:
        # Preserve FastAPI's omitted-model sentinel so return annotations can be
        # inferred separately from Zodiac's response_model=None -> Any contract.
        response_model_is_default = isinstance(response_model, DefaultPlaceholder)
        body_allowed = is_body_allowed_for_status_code(kwargs.get("status_code"))
        return_annotation = get_typed_return_annotation(endpoint)
        raw_return_annotation = _unwrap_annotated(return_annotation)
        returns_raw_response = lenient_issubclass(raw_return_annotation, FastAPIResponse)

        if response_model_is_default:
            if returns_raw_response:
                response_model = None
            elif return_annotation is None:
                response_model = Any if body_allowed else None
            else:
                response_model = return_annotation
        elif response_model is None and body_allowed and not returns_raw_response:
            response_model = Any

        # 1. Wrap the inferred or explicit main response model.
        if self._should_wrap(response_model):
            response_model = self._wrap_response_model(response_model)

        # 2. Wrap additional responses (e.g. 400, 404 models)
        # Copy to avoid mutating caller's dict
        if responses:
            responses = {code: {**res_dict} for code, res_dict in responses.items()}
            for res in responses.values():
                if "model" in res and self._should_wrap(res["model"]):
                    res["model"] = self._wrap_response_model(res["model"])

        # 3. Body-bearing endpoints always apply the runtime wrapper. The result
        # check passes actual FastAPI/Starlette Response objects through unchanged.
        if body_allowed:
            endpoint = self._wrap_endpoint(endpoint)

        super().__init__(
            path,
            endpoint,
            response_model=response_model,
            responses=responses,
            **kwargs,
        )

    @staticmethod
    def _should_wrap(model: Any) -> bool:
        """Check if a model needs to be wrapped with Response[T]."""
        if model is None:
            return False
        if model is Any:
            return True
        origin = get_origin(model)
        if origin is Response:
            return False
        try:
            if isinstance(model, type) and issubclass(model, Response):
                return False
        except TypeError:
            pass
        return True

    @staticmethod
    def _wrap_response_model(model: Any) -> type[Response]:
        """Wrap a model type with Response[T] using Pydantic's native generics."""
        return Response[model]

    @staticmethod
    def _maybe_wrap_result(result: Any) -> Any:
        """Wrap result in Response if not already a Response type."""
        if isinstance(result, (Response, FastAPIResponse)):
            return result
        return Response(data=result)

    @staticmethod
    def _wrap_endpoint(endpoint: Callable) -> Callable:
        """Wrap endpoint to automatically wrap return values in Response."""

        @wraps(endpoint)
        async def async_wrapper(*args, **kwargs):
            result = await endpoint(*args, **kwargs)
            return ZodiacRoute._maybe_wrap_result(result)

        @wraps(endpoint)
        def sync_wrapper(*args, **kwargs):
            result = endpoint(*args, **kwargs)
            return ZodiacRoute._maybe_wrap_result(result)

        return async_wrapper if inspect.iscoroutinefunction(endpoint) else sync_wrapper


class APIRouter(FastAPIRouter):
    """
    Zodiac-enhanced APIRouter that uses ZodiacRoute by default.

    Body-bearing routes registered via this router will, by default:
    - Infer omitted response models from endpoint return annotations
    - Wrap response models with Response[T] for OpenAPI docs
    - Wrap endpoint return values with the Response structure

    response_model=None keeps the envelope with an unconstrained Any payload.
    Return a FastAPI/Starlette Response object to bypass runtime wrapping.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("route_class", ZodiacRoute)
        super().__init__(*args, **kwargs)
