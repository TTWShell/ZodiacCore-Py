"""
Unified cache layer: config (setup) + prefix + @cached decorator.

Install: pip install 'zodiac-core[cache]'

Example:

    from zodiac_core.cache import cache, cached, ZodiacCache

    # Configure once (e.g. in app lifespan)
    cache.setup(prefix="svc-user", default_ttl=300)

    # Decorate async functions to cache by (fn + args)
    @cached(ttl=60)
    async def get_user(user_id: int):
        return await db.fetch_user(user_id)

    # Or use the cache instance directly
    c = cache.cache
    await c.get_or_set("entity:123", load_user, ttl=300)
"""

from zodiac_core.cache.decorators import cached
from zodiac_core.cache.manager import ZodiacCache, cache

__all__ = ["cache", "cached", "ZodiacCache"]
