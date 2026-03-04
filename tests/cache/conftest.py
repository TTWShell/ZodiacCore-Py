"""Shared fixtures for zodiac_core.cache tests (requires aiocache)."""

import pytest

pytest.importorskip("aiocache")

from aiocache import caches

from zodiac_core.cache import cache
from zodiac_core.cache.manager import DEFAULT_CACHE_NAME


def _clear_default_from_aiocache():
    cache._wrappers.clear()
    getattr(caches, "_caches", {}).pop(DEFAULT_CACHE_NAME, None)
    getattr(caches, "_config", {}).pop(DEFAULT_CACHE_NAME, None)


@pytest.fixture(autouse=True)
def reset_cache_manager():
    """Reset cache state before and after each test so tests don't leak (aiocache has default in _config at import)."""
    _clear_default_from_aiocache()
    yield
    _clear_default_from_aiocache()
