from typing import Any, Callable, get_origin, get_args, Dict, Optional, Union, List
from functools import wraps
import inspect

from fastapi import Response as FastAPIResponse, APIRouter as FastAPIRouter
from fastapi.routing import APIRoute
from fastapi.datastructures import DefaultPlaceholder
from pydantic import create_model

from zodiac_core.response import Response


def _get_model_name(model: Any) -> str:
    if hasattr(model, "__name__"):
        return model.__name__
    origin = get_origin(model)
    if origin in (list, List):
        args = get_args(model)
        return f"List_{_get_model_name(args[0])}" if args else "List"
    return "Data"


class ZodiacRoute(APIRoute):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        response_model: Any = None,
        responses: Optional[Dict[Union[int, str], Dict[str, Any]]] = None,
        **kwargs
    ) -> None:
        # Resolve Placeholder
        if isinstance(response_model, DefaultPlaceholder):
            response_model = response_model.value

        # 1. Wrap main response model (Default to Any if missing)
        if self._should_wrap(response_model):
            response_model = self._wrap_response_model(response_model or Any)

        # 2. Wrap additional responses (e.g. 400, 404 models)
        if responses:
            for res in responses.values():
                if "model" in res and self._should_wrap(res["model"]):
                    res["model"] = self._wrap_response_model(res["model"])

        # 3. Wrap endpoint
        endpoint = self._wrap_endpoint(endpoint)

        super().__init__(
            path,
            endpoint,
            response_model=response_model,
            responses=responses,
            **kwargs
        )

    @staticmethod
    def _should_wrap(model: Any) -> bool:
        if model is Any or model is None:
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
    def _wrap_response_model(model: Any) -> Any:
        name = f"Response_{_get_model_name(model)}"
        return create_model(
            name,
            __base__=Response,
            __module__=Response.__module__,
            data=(Optional[model], None),
            code=(int, 0),
            message=(str, "Success"),
        )

    @staticmethod
    def _wrap_endpoint(endpoint: Callable) -> Callable:
        @wraps(endpoint)
        async def async_wrapper(*args, **kwargs):
            result = await endpoint(*args, **kwargs)
            if isinstance(result, (Response, FastAPIResponse)):
                return result
            return Response(code=0, data=result, message="Success")

        @wraps(endpoint)
        def sync_wrapper(*args, **kwargs):
            result = endpoint(*args, **kwargs)
            if isinstance(result, (Response, FastAPIResponse)):
                return result
            return Response(code=0, data=result, message="Success")

        return async_wrapper if inspect.iscoroutinefunction(endpoint) else sync_wrapper


class APIRouter(FastAPIRouter):
    """
    Zodiac-enhanced APIRouter that uses ZodiacRoute by default.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("route_class", ZodiacRoute)
        super().__init__(*args, **kwargs)
