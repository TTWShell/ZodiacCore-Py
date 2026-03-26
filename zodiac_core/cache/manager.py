"""
Unified cache layer: config (setup) + prefix + @cached decorator.
"""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any, Dict, Optional, TypeVar

try:
    from aiocache import caches as aiocaches
    from aiocache.base import BaseCache
    from aiocache.lock import RedLock
except ImportError as e:
    raise ImportError(
        "aiocache is required to use the 'zodiac_core.cache' module. "
        "Please install it with: pip install 'zodiac-core[cache]'"
    ) from e

from loguru import logger

ZODIAC_CACHE_NAMESPACE = "zodiac_cache"
DEFAULT_CACHE_NAME = "default"


class _CachedNoneSentinel:
    """Internal sentinel to distinguish between a cache miss and a cached None."""

    pass


_CACHED_NONE = _CachedNoneSentinel()

T = TypeVar("T")


class ZodiacCache:
    """
    Thin wrapper over aiocache BaseCache with stampede protection.
    """

    def __init__(
        self,
        backend: BaseCache,
        *,
        default_ttl: Optional[int] = None,
    ) -> None:
        self._backend = backend
        self._default_ttl = default_ttl

    @property
    def backend(self) -> BaseCache:
        """The underlying aiocache backend instance."""
        return self._backend

    async def _get_raw(self, key: str) -> Any:
        """Retrieve the raw backend value, including internal sentinels."""
        return await self._backend.get(key)

    async def get(self, key: str) -> Any:
        """Retrieve a value from the cache."""
        value = await self._get_raw(key)
        if isinstance(value, _CachedNoneSentinel):
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value in the cache with an optional TTL."""
        ttl = ttl if ttl is not None else self._default_ttl
        return await self._backend.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        """Remove a value from the cache."""
        return await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        return await self._backend.exists(key)

    async def get_or_set(
        self,
        key: str,
        producer: Callable[[], Awaitable[T]],
        ttl: Optional[int] = None,
        lease: Optional[float] = 2.0,
        skip_cache_func: Optional[Callable[[T], bool]] = None,
    ) -> T:
        """
        Get from cache, or call producer and set on miss with RedLock protection.

        Args:
            key: Cache key.
            producer: Async callable to compute the value.
            ttl: TTL in seconds.
            lease: Lock lease in seconds for stampede protection.
            skip_cache_func: If it returns True, the produced value is not stored.
        """
        value = await self._get_raw(key)
        if isinstance(value, _CachedNoneSentinel):
            return None
        if value is not None:
            return value

        lease_sec = lease if lease is not None and lease > 0 else 2.0
        async with RedLock(self._backend, key, lease=lease_sec):
            value = await self._get_raw(key)
            if isinstance(value, _CachedNoneSentinel):
                return None
            if value is not None:
                return value

            fresh = await producer()
            if skip_cache_func is not None and skip_cache_func(fresh):
                return fresh

            to_store = _CACHED_NONE if fresh is None else fresh
            await self.set(key, to_store, ttl=ttl)
            return fresh

    async def close(self) -> None:
        """Close the underlying backend connections."""
        await self._backend.close()


class CacheManager:
    """
    Singleton manager for ZodiacCache instances.
    Aligns with aiocache.caches and mirrors DatabaseManager.
    """

    _instance = None

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._wrappers: Dict[str, ZodiacCache] = {}
            cls._instance._setup_configs: Dict[str, Dict[str, Any]] = {}
        return cls._instance

    def get_cache(self, name: str = DEFAULT_CACHE_NAME) -> ZodiacCache:
        """Return the cache instance (ZodiacCache) for the given name."""
        if name not in self._wrappers:
            try:
                backend = aiocaches.get(name)
            except Exception as e:
                raise RuntimeError(f"Cache '{name}' is not initialized: {e}") from e
            setup_config = self._setup_configs.get(name, {})
            self._wrappers[name] = ZodiacCache(
                backend=backend,
                default_ttl=setup_config.get("default_ttl"),
            )
        return self._wrappers[name]

    @property
    def cache(self) -> ZodiacCache:
        """The default cache instance (ZodiacCache) for get/set/get_or_set."""
        return self.get_cache(DEFAULT_CACHE_NAME)

    def setup(
        self,
        prefix: str,
        *,
        name: str = DEFAULT_CACHE_NAME,
        default_ttl: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """
        Configure a cache using aiocache's unified config. All ``kwargs`` are
        passed through to aiocache (e.g. ``cache``, ``endpoint``, ``port``,
        ``serializer``, ``ttl``). We only set default ``namespace`` to
        ``{ZODIAC_CACHE_NAMESPACE}:{prefix}`` and minimal defaults (cache class,
        serializer) when omitted.
        """
        config = dict(kwargs)
        config["namespace"] = f"{ZODIAC_CACHE_NAMESPACE}:{prefix}"  # always apply our namespace
        config.setdefault("cache", "aiocache.SimpleMemoryCache")
        config.setdefault("serializer", {"class": "aiocache.serializers.PickleSerializer"})

        if name in self._wrappers:
            existing = self._setup_configs.get(name)
            current = {"default_ttl": default_ttl, "config": config}
            if existing == current:
                logger.debug(f"Cache '{name}' is already configured with the same settings, skipping.")
                return
            raise RuntimeError(f"Cache '{name}' is already configured with different settings")

        aiocaches.add(name, config)
        instance = aiocaches.get(name)
        self._wrappers[name] = ZodiacCache(backend=instance, default_ttl=default_ttl)
        self._setup_configs[name] = {"default_ttl": default_ttl, "config": deepcopy(config)}
        logger.info(f"Cache '{name}' initialized with prefix={prefix}")

    async def shutdown(self, name: str | None = None) -> None:
        """
        Close cache resources and remove them from aiocache's registry.

        Args:
            name: Optional cache name. When provided, only that cache is closed
                  and deregistered. When omitted, all registered caches are closed.
        """
        if name is not None:
            wrapper = self._wrappers.pop(name, None)
            if wrapper is not None:
                await wrapper.close()
            getattr(aiocaches, "_caches", {}).pop(name, None)
            getattr(aiocaches, "_config", {}).pop(name, None)
            self._setup_configs.pop(name, None)
            return

        for cache_name, wrapper in list(self._wrappers.items()):
            await wrapper.close()
            getattr(aiocaches, "_caches", {}).pop(cache_name, None)
            getattr(aiocaches, "_config", {}).pop(cache_name, None)
            del self._wrappers[cache_name]
            self._setup_configs.pop(cache_name, None)


cache = CacheManager()
