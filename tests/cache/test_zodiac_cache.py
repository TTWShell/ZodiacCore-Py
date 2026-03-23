"""Tests for ZodiacCache (get/set/delete/get_or_set, namespace, RedLock)."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from aiocache import Cache

from zodiac_core.cache import ZodiacCache
from zodiac_core.cache import manager as cache_manager_module
from zodiac_core.cache.manager import _CACHED_NONE


class TestZodiacCachePrefix:
    """Unified key prefix behavior using native namespace."""

    @pytest.mark.asyncio
    async def test_prefix_applied_to_keys(self):
        # Using native namespace support
        backend1 = Cache(namespace="svc-user")
        cache1 = ZodiacCache(backend1)
        await cache1.set("entity:1", "alice")
        assert await cache1.get("entity:1") == "alice"

        # Same logical key with different prefix must not collide
        backend2 = Cache(namespace="svc-order")
        cache2 = ZodiacCache(backend2)
        assert await cache2.get("entity:1") is None
        await cache2.set("entity:1", "order-1")

        assert await cache1.get("entity:1") == "alice"
        assert await cache2.get("entity:1") == "order-1"


class TestZodiacCacheGetSetDelete:
    """Basic get/set/delete/exists."""

    @pytest.fixture
    def zc(self):
        backend = Cache(namespace="test")
        return ZodiacCache(backend, default_ttl=60)

    @pytest.mark.asyncio
    async def test_set_get_roundtrip(self, zc):
        await zc.set("a", "value")
        assert await zc.get("a") == "value"
        await zc.set("b", 42)
        assert await zc.get("b") == 42

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, zc):
        assert await zc.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_delete(self, zc):
        await zc.set("k", "v")
        assert await zc.get("k") == "v"
        await zc.delete("k")
        assert await zc.get("k") is None

    @pytest.mark.asyncio
    async def test_exists(self, zc):
        assert await zc.exists("x") is False
        await zc.set("x", 1)
        assert await zc.exists("x") is True
        await zc.delete("x")
        assert await zc.exists("x") is False

    @pytest.mark.asyncio
    async def test_close_no_error(self, zc):
        await zc.close()


class TestZodiacCacheGetOrSet:
    """Auto-refresh via get_or_set with stampede protection."""

    @pytest.mark.asyncio
    async def test_get_or_set_miss_calls_producer_and_caches(self):
        backend = Cache(namespace="test")
        zc = ZodiacCache(backend, default_ttl=300)
        call_count = 0

        async def producer():
            nonlocal call_count
            call_count += 1
            return "fresh"

        out1 = await zc.get_or_set("k", producer)
        assert out1 == "fresh"
        assert call_count == 1
        out2 = await zc.get_or_set("k", producer)
        assert out2 == "fresh"
        assert call_count == 1
        assert await zc.get("k") == "fresh"

    @pytest.mark.asyncio
    async def test_get_or_set_stampede_protection(self):
        backend = Cache(namespace="stampede")
        zc = ZodiacCache(backend)
        call_count = 0

        async def slow_producer():
            nonlocal call_count
            await asyncio.sleep(0.1)
            call_count += 1
            return "data"

        tasks = [zc.get_or_set("k", slow_producer) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(r == "data" for r in results)
        assert call_count == 1  # RedLock: only one producer runs

    @pytest.mark.asyncio
    async def test_get_or_set_lease_defaults(self):
        """lease=0 or lease=None falls back to 2s, RedLock still applies."""
        backend = Cache(namespace="lease")
        zc = ZodiacCache(backend)
        call_count = 0

        async def producer():
            nonlocal call_count
            await asyncio.sleep(0.05)
            call_count += 1
            return "v"

        # lease=0 -> treated as 2, should still serialize
        out = await zc.get_or_set("k", producer, lease=0)
        assert out == "v"
        assert call_count == 1
        assert await zc.get("k") == "v"

        # lease=None -> same
        call_count = 0
        out2 = await zc.get_or_set("k2", producer, lease=None)
        assert out2 == "v"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_or_set_skip_cache_func(self):
        """When skip_cache_func returns True, value is returned but not stored."""
        backend = Cache(namespace="skip")
        zc = ZodiacCache(backend)
        call_count = 0

        async def producer_none():
            nonlocal call_count
            call_count += 1
            return None

        out = await zc.get_or_set("k", producer_none, skip_cache_func=lambda r: r is None)
        assert out is None
        assert call_count == 1
        assert await zc.get("k") is None  # not stored
        out2 = await zc.get_or_set("k", producer_none, skip_cache_func=lambda r: r is None)
        assert out2 is None
        assert call_count == 2  # producer ran again

    @pytest.mark.asyncio
    async def test_get_or_set_caches_none_when_no_skip(self):
        """When skip_cache_func is not passed, None is stored (via sentinel); second call from cache."""
        backend = Cache(namespace="cached_none")
        zc = ZodiacCache(backend)
        call_count = 0

        async def producer_none():
            nonlocal call_count
            call_count += 1
            return None

        out1 = await zc.get_or_set("k", producer_none)
        assert out1 is None
        assert call_count == 1
        out2 = await zc.get_or_set("k", producer_none)
        assert out2 is None
        assert call_count == 1  # from cache

    @pytest.mark.asyncio
    async def test_get_returns_none_after_cached_none(self):
        """Public get() should decode the internal sentinel back to None."""
        backend = Cache(namespace="cached_none_get")
        zc = ZodiacCache(backend)

        async def producer_none():
            return None

        out = await zc.get_or_set("k", producer_none)
        assert out is None
        assert await zc.get("k") is None

    @pytest.mark.asyncio
    async def test_get_or_set_returns_none_when_lock_recheck_hits_cached_none(self, monkeypatch):
        """If another worker stores cached None before the lock recheck, get_or_set should return None."""
        backend = Cache(namespace="cached_none_recheck")
        zc = ZodiacCache(backend)
        values = iter([None, _CACHED_NONE])

        async def fake_get_raw(_key: str):
            return next(values)

        @asynccontextmanager
        async def fake_redlock(*args, **kwargs):
            yield

        monkeypatch.setattr(zc, "_get_raw", fake_get_raw)
        monkeypatch.setattr(cache_manager_module, "RedLock", fake_redlock)

        producer_called = False

        async def producer():
            nonlocal producer_called
            producer_called = True
            return "fresh"

        out = await zc.get_or_set("k", producer)
        assert out is None
        assert producer_called is False
