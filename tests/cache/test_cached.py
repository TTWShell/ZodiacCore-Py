"""Tests for @cached decorator (key from fn+args, name, skip_cache_func, exceptions)."""

import pytest

from zodiac_core.cache import cache, cached
from zodiac_core.cache.manager import ZODIAC_CACHE_NAMESPACE


class TestCachedDecorator:
    """@cached decorator uses configured cache and key from fn+args."""

    @pytest.mark.asyncio
    async def test_cached_miss_then_hit(self):
        cache.setup(prefix="deco", default_ttl=300)
        calls = 0

        @cached(ttl=60)
        async def fetch(x: int):
            nonlocal calls
            calls += 1
            return x * 2

        assert await fetch(1) == 2
        assert calls == 1
        assert await fetch(1) == 2
        assert calls == 1
        assert await fetch(2) == 4
        assert calls == 2

    @pytest.mark.asyncio
    async def test_cached_sync_function_supported(self):
        """@cached works with sync functions; decorated callable is async, so caller must await."""
        cache.setup(prefix="deco_sync", default_ttl=300)
        calls = 0

        @cached(ttl=60)
        def fetch_sync(x: int):
            nonlocal calls
            calls += 1
            return x * 3

        assert await fetch_sync(1) == 3
        assert calls == 1
        assert await fetch_sync(1) == 3
        assert calls == 1
        assert await fetch_sync(2) == 6
        assert calls == 2

    @pytest.mark.asyncio
    async def test_cached_without_setup_raises(self):
        """Calling a @cached function before cache.setup() raises RuntimeError."""

        @cached(ttl=60)
        async def fn():
            return 1

        with pytest.raises(RuntimeError, match="not initialized"):
            await fn()  # cache.cache used by @cached

    @pytest.mark.asyncio
    async def test_cached_exception_not_cached(self):
        """When decorated function raises, exception propagates and nothing is stored."""
        cache.setup(prefix="deco_err", default_ttl=300)
        calls = 0

        @cached(ttl=60)
        async def failing(x: int):
            nonlocal calls
            calls += 1
            raise ValueError("fail")

        with pytest.raises(ValueError, match="fail"):
            await failing(1)
        assert calls == 1
        # Second call runs again (no cached value)
        with pytest.raises(ValueError, match="fail"):
            await failing(1)
        assert calls == 2

    @pytest.mark.asyncio
    async def test_cached_none_not_stored_by_default(self):
        """By default None is not cached; next call runs the function again."""
        cache.setup(prefix="deco_none", default_ttl=300)
        calls = 0

        @cached(ttl=60)
        async def return_none(x: int):
            nonlocal calls
            calls += 1
            return None

        assert await return_none(1) is None
        assert calls == 1
        assert await return_none(1) is None
        assert calls == 2  # ran again, not from cache

    @pytest.mark.asyncio
    async def test_cached_skip_cache_func_allow_none(self):
        """skip_cache_func=lambda r: False allows caching None."""
        cache.setup(prefix="deco_allow_none", default_ttl=300)
        calls = 0

        @cached(ttl=60, skip_cache_func=lambda r: False)
        async def return_none(x: int):
            nonlocal calls
            calls += 1
            return None

        assert await return_none(1) is None
        assert calls == 1
        assert await return_none(1) is None
        assert calls == 1  # from cache

    @pytest.mark.asyncio
    async def test_cached_with_name_uses_named_cache(self):
        """@cached(name='other') uses cache.get_cache('other')."""
        cache.setup(prefix="default", default_ttl=60, name="default")
        cache.setup(prefix="other", default_ttl=120, name="other")
        calls = 0

        @cached(ttl=30, name="other")
        async def fetch():
            nonlocal calls
            calls += 1
            return "from_other"

        out = await fetch()
        assert out == "from_other"
        assert calls == 1
        out2 = await fetch()
        assert out2 == "from_other"
        assert calls == 1
        # Named cache has namespace zodiac_cache:other
        assert cache.get_cache("other").backend.namespace == f"{ZODIAC_CACHE_NAMESPACE}:other"

    @pytest.mark.asyncio
    async def test_cached_key_builder_fallback_when_pickle_fails(self):
        """Default key_builder falls back to repr hash when pickle.dumps raises (e.g. lambda in args)."""
        cache.setup(prefix="deco_fallback", default_ttl=300)
        calls = 0

        @cached(ttl=60)
        async def fn(x):
            nonlocal calls
            calls += 1
            return 42  # picklable so cache can store it

        # Unpicklable arg triggers except branch in key_builder; same ref => same key => cache hit
        def unpicklable():
            return 1

        assert await fn(unpicklable) == 42
        assert calls == 1
        assert await fn(unpicklable) == 42
        assert calls == 1
