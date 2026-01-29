from typing import Any, Dict, Optional

import httpx
from loguru import logger

from zodiac_core.context import get_request_id


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
