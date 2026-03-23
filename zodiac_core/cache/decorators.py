"""
@cached decorator: cache async or sync function result using the configured default cache.
"""

import hashlib
import inspect
import pickle
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Optional, TypeVar

from zodiac_core.cache.manager import cache as _default_cache_manager

T = TypeVar("T")


def _skip_none(result: Any) -> bool:
    """Default: do not cache None (avoids ambiguity with cache miss)."""
    return result is None


def _normalize_key_part(value: Any) -> Any:
    """Normalize supported arguments into a stable structure for the default key builder."""
    if value is None or isinstance(value, bool | int | float | str | bytes):
        return value
    if isinstance(value, tuple):
        return tuple(_normalize_key_part(item) for item in value)
    raise TypeError(f"unsupported type {type(value).__qualname__}")


def _default_key_builder(
    fn: Callable[..., Awaitable[Any]],
    args: tuple,
    kwargs: dict,
) -> str:
    """Build cache key from function identity and supported immutable arguments."""
    base = f"{fn.__module__}:{fn.__qualname__}"
    try:
        normalized_args = tuple(_normalize_key_part(arg) for arg in args)
        normalized_kwargs = tuple((key, _normalize_key_part(value)) for key, value in sorted(kwargs.items()))
    except TypeError as e:
        raise TypeError(
            f"Unsupported argument type for cached key in {base}; provide key_builder explicitly for complex parameters"
        ) from e
    raw = pickle.dumps((normalized_args, normalized_kwargs))
    h = hashlib.sha256(raw).hexdigest()[:16]
    return f"{base}:{h}"


def cached(
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[[Callable[..., Awaitable[T]], tuple, dict], str]] = None,
    name: Optional[str] = None,
    skip_cache_func: Optional[Callable[[T], bool]] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorate an async or sync function to cache its return value with the configured cache.
    The decorated callable is always async (await the result). Sync functions are called
    inside the cache layer; avoid slow blocking sync work to not block the event loop.

    Uses ``cache.get_cache(name)`` when ``name`` is set, otherwise ``cache.cache`` (default).
    Key is built from module, qualname, and supported immutable args/kwargs
    (or a custom key_builder).
    TTL comes from decorator, then from the cache instance default_ttl.

    **Exception handling:** If the wrapped function raises, the exception
    propagates and nothing is written to the cache.

    **None and skip_cache_func:** By default, a return value of ``None`` is
    *not* stored (so the next call will run the function again). This avoids
    ambiguity with cache miss. To cache ``None``, pass
    ``skip_cache_func=lambda r: False``. To skip caching other values (e.g.
    empty list), pass a callable that returns True for values that must not
    be cached.

    Args:
        ttl: TTL in seconds for this function's entries. If None, uses cache default_ttl.
        key_builder: Optional (fn, args, kwargs) -> str. Default supports stable
            immutable parameters only; provide explicitly for complex types.
        name: Name of the cache (from cache.setup(..., name=...)). If None, uses default.
        skip_cache_func: Callable(result) -> bool; if True, result is not stored.
            Default is to skip when result is None.
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        builder = key_builder or _default_key_builder
        skip = skip_cache_func if skip_cache_func is not None else _skip_none

        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            backend = _default_cache_manager.get_cache(name) if name is not None else _default_cache_manager.cache
            key = builder(fn, args, kwargs)

            async def producer() -> T:
                if inspect.iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                return fn(*args, **kwargs)

            return await backend.get_or_set(key, producer, ttl=ttl, skip_cache_func=skip)

        return wrapper

    return decorator
