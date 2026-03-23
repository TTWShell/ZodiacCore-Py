"""Tests for CacheManager (setup / get_cache / shutdown)."""

import pytest
from aiocache import caches

from zodiac_core.cache import cache
from zodiac_core.cache.manager import DEFAULT_CACHE_NAME, ZODIAC_CACHE_NAMESPACE


class TestCacheManager:
    """Config-driven cache (setup / get_cache / cache)."""

    @pytest.mark.asyncio
    async def test_cache_without_setup_raises(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = cache.cache

    @pytest.mark.asyncio
    async def test_setup_and_get_cache(self):
        cache.setup(prefix="svc-test", default_ttl=60)
        c = cache.cache
        assert c.backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:svc-test"
        await c.set("a", 1)
        assert await c.get("a") == 1

    @pytest.mark.asyncio
    async def test_setup_with_custom_kwargs(self):
        cache.setup(prefix="custom", default_ttl=10, ttl=20)
        c = cache.cache
        assert c.backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:custom"

    @pytest.mark.asyncio
    async def test_setup_accepts_aiocache_params_applies_namespace(self):
        """kwargs are aiocache config; we only set default namespace."""
        cache.setup(
            prefix="myapp",
            cache="aiocache.SimpleMemoryCache",
            serializer={"class": "aiocache.serializers.PickleSerializer"},
            default_ttl=60,
        )
        c = cache.cache
        assert c.backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:myapp"
        await c.set("x", 42)
        assert await c.get("x") == 42

    @pytest.mark.asyncio
    async def test_setup_with_alias_config_spread(self):
        """Pass **get_alias_config(alias) to reuse alias config; we override namespace."""
        caches.add(
            "test_zodiac_alias",
            {
                "cache": "aiocache.SimpleMemoryCache",
                "namespace": "from_alias",
                "serializer": {"class": "aiocache.serializers.PickleSerializer"},
            },
        )
        try:
            config = caches.get_alias_config("test_zodiac_alias")
            cache.setup(prefix="app", **config)
            c = cache.cache
            assert c.backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:app"
            await c.set("k", 1)
            assert await c.get("k") == 1
        finally:
            if "test_zodiac_alias" in caches._config:
                del caches._config["test_zodiac_alias"]
            if "test_zodiac_alias" in getattr(caches, "_caches", {}):
                caches._caches.pop("test_zodiac_alias", None)

    @pytest.mark.asyncio
    async def test_get_cache_returns_same_instance(self):
        """get_cache(name) returns the same ZodiacCache when called twice."""
        cache.setup(prefix="same", default_ttl=60)
        c1 = cache.get_cache(DEFAULT_CACHE_NAME)
        c2 = cache.get_cache(DEFAULT_CACHE_NAME)
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_get_cache_rebuilds_wrapper_from_existing_aiocache_alias(self):
        """get_cache(name) should rebuild the ZodiacCache wrapper if only the wrapper cache was cleared."""
        cache.setup(prefix="same", default_ttl=60)
        original = cache.cache

        cache._wrappers.clear()

        rebuilt = cache.get_cache(DEFAULT_CACHE_NAME)
        assert rebuilt is not original
        assert rebuilt.backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:same"
        assert rebuilt._default_ttl == 60

    @pytest.mark.asyncio
    async def test_setup_same_name_twice_with_same_config_is_idempotent(self):
        """Setup with the same config again is idempotent."""
        cache.setup(prefix="idem", default_ttl=60)
        first = cache.cache
        cache.setup(prefix="idem", default_ttl=60)
        second = cache.get_cache(DEFAULT_CACHE_NAME)
        assert first is second

    @pytest.mark.asyncio
    async def test_setup_same_name_with_different_config_raises(self):
        """Setup with different settings for the same name should fail fast."""
        cache.setup(prefix="idem", default_ttl=60)

        with pytest.raises(RuntimeError, match="already configured with different settings"):
            cache.setup(prefix="idem", default_ttl=120)

    @pytest.mark.asyncio
    async def test_shutdown_closes_and_removes_backend(self):
        """shutdown() closes wrappers and removes backends from aiocache; cache.cache then raises."""
        cache.setup(prefix="shutdown_test", default_ttl=60)
        c = cache.cache
        await c.set("x", 1)
        await cache.shutdown()
        assert DEFAULT_CACHE_NAME not in cache._wrappers
        assert DEFAULT_CACHE_NAME not in cache._setup_configs
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = cache.cache
