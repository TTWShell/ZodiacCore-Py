from contextlib import asynccontextmanager
from functools import wraps
from inspect import iscoroutinefunction
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    NoReturn,
    Optional,
    ParamSpec,
    TypeVar,
)

import httpx
from loguru import logger

from zodiac_core.context import get_request_id
from zodiac_core.exceptions import UpstreamRequestError, UpstreamServiceError

P = ParamSpec("P")
R = TypeVar("R")


def _inject_header(request: httpx.Request) -> None:
    """Core logic to inject Trace ID into request headers."""
    request_id = get_request_id()
    if request_id:
        request.headers["X-Request-ID"] = request_id
        logger.debug(f"Injected Trace ID {request_id} into request to {request.url}")


async def _inject_trace_id_async_hook(request: httpx.Request) -> None:
    """Async httpx event hook."""
    _inject_header(request)


def _inject_trace_id_hook(request: httpx.Request) -> None:
    """Sync httpx event hook."""
    _inject_header(request)


def _merge_hooks(user_hooks: Optional[Dict[str, Any]], trace_hook: Any) -> Dict[str, Any]:
    """Helper to safely merge user provided hooks with our trace injector."""
    hooks = (user_hooks or {}).copy()
    request_hooks = hooks.get("request", [])

    if not isinstance(request_hooks, list):
        request_hooks = [request_hooks]
    else:
        request_hooks = list(request_hooks)  # Create a copy to avoid side effects

    request_hooks.append(trace_hook)
    hooks["request"] = request_hooks
    return hooks


def _raise_upstream_error(
    service: str,
    exc: httpx.HTTPStatusError | httpx.RequestError,
) -> NoReturn:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        logger.warning(
            "Upstream HTTP error service={} status_code={}",
            service,
            status_code,
        )
        if status_code in (400, 422):
            raise UpstreamRequestError(
                service=service,
                upstream_status=status_code,
            ) from exc
        raise UpstreamServiceError(
            service=service,
            upstream_status=status_code,
        ) from exc

    logger.warning(
        "Upstream request error service={} error_type={}",
        service,
        exc.__class__.__name__,
    )
    raise UpstreamServiceError(service=service) from exc


def translate_upstream_errors(service: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Convert httpx upstream failures into standardized ZodiacCore exceptions.

    Decorated functions should call ``response.raise_for_status()`` after
    receiving an ``httpx.Response`` so HTTP status failures can be classified.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    _raise_upstream_error(service, exc)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                _raise_upstream_error(service, exc)

        return sync_wrapper

    return decorator


class ZodiacClient(httpx.AsyncClient):
    """
    A wrapper around httpx.AsyncClient that automatically injects
    the current Trace ID into outgoing requests.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        event_hooks: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        super().__init__(
            timeout=timeout,
            event_hooks=_merge_hooks(event_hooks, _inject_trace_id_async_hook),
            **kwargs,
        )


class ZodiacSyncClient(httpx.Client):
    """
    A wrapper around httpx.Client that automatically injects
    the current Trace ID into outgoing requests.
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        event_hooks: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        super().__init__(
            timeout=timeout,
            event_hooks=_merge_hooks(event_hooks, _inject_trace_id_hook),
            **kwargs,
        )


@asynccontextmanager
async def init_http_client(
    *,
    timeout: float = 30.0,
    event_hooks: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> AsyncGenerator[ZodiacClient, None]:
    """Create and close a shared ZodiacClient within an application lifecycle."""
    async with ZodiacClient(timeout=timeout, event_hooks=event_hooks, **kwargs) as client:
        yield client
