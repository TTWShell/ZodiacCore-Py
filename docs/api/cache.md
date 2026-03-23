# Cache (Unified Layer)

Unified cache on **aiocache**: one-time `cache.setup`, global default cache, stampede-protected `get_or_set` and `@cached`.

## 1. Core concepts

- **cache** (CacheManager): singleton; `cache.setup(prefix=...)` once, then `cache.cache` (or `cache.get_cache(name)`) and `@cached` use it.
- **ZodiacCache**: thin wrapper over aiocache `BaseCache` — `get` / `set` / `delete` / `exists` and **get_or_set** (RedLock stampede protection).
- **Namespace**: `cache.setup(prefix="...")` → keys under `zodiac_cache:{prefix}`.

---

## 2. Installation

```bash
pip install 'zodiac-core[cache]'
```

Requires `aiocache>=0.12.0`. For Redis etc., see [aiocache docs](https://aiocache.aio-libs.org/en/latest/).

---

## 3. Configuration

Call `cache.setup` at startup; optionally `await cache.shutdown()` on shutdown.

### In-memory (default)

Pass only `prefix` (and optional `default_ttl`). We set default `cache` and `serializer`; namespace is always `zodiac_cache:{prefix}`.

```python
from zodiac_core.cache import cache

cache.setup(prefix="myapp", default_ttl=300)
```

### Custom backend (Redis, etc.)

Use aiocache's same parameters as `caches.add()`. We only inject/override `namespace` and minimal defaults.

```python
cache.setup(
    prefix="myapp",
    cache="aiocache.RedisCache",
    endpoint="127.0.0.1",
    port=6379,
    default_ttl=300,
)
```

To reuse an existing alias config: `cache.setup(prefix="myapp", **caches.get_alias_config("my_redis"))`. Namespace is still set to `zodiac_cache:myapp`.

### Named caches (`name`)

You can register multiple caches under different names (e.g. default in-memory + a Redis cache for sessions). Use the **`name`** parameter:

- **In `cache.setup(prefix=..., name=...)`**
  Registers a cache under that name. Default is `"default"`. Each name has its own backend config and namespace `zodiac_cache:{prefix}`. Example: `cache.setup(prefix="myapp", default_ttl=300)` uses `name="default"`; `cache.setup(prefix="sessions", name="sessions", cache="aiocache.RedisCache", endpoint="...")` adds a second cache.

- **`cache.cache`**
  Shorthand for `cache.get_cache("default")` (the default cache).

- **`cache.get_cache(name)`**
  Returns the `ZodiacCache` for that name. Use this when you have multiple caches and want to call `get` / `set` / `get_or_set` on a specific one.

- **In `@cached(..., name=...)`**
  The decorator uses that named cache instead of the default. Example: `@cached(ttl=60, name="sessions")` stores entries in the cache registered with `name="sessions"`.

Typical use: one default cache (e.g. in-memory or Redis) plus an optional second cache (e.g. Redis for sessions) with a different backend or TTL; call `cache.get_cache("sessions")` or `@cached(name="sessions")` for the second one.

### FastAPI lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from zodiac_core.cache import cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    cache.setup(prefix="myapp", default_ttl=300)
    yield
    await cache.shutdown()

app = FastAPI(lifespan=lifespan)
```

---

## 4. Usage

**get_or_set:** `c = cache.cache` then `await c.get_or_set("key", producer, ttl=60)`.

**@cached:** Key from `module:qualname:hash(args,kwargs)`. The default key builder only supports stable immutable parameters (`None`, `bool`, `int`, `float`, `str`, `bytes`, and tuples of those values). Supports both **async** and **sync** functions.

> **Important:** The decorated function **always becomes asynchronous**. If you decorate a sync function, you must still `await` the result. Avoid slow blocking work in sync functions to prevent blocking the event loop.

```python
from zodiac_core.cache import cache, cached

cache.setup(prefix="myapp", default_ttl=300)

# Async function (standard usage)
@cached(ttl=60)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)

# Sync function (now supported, but caller MUST await)
@cached(ttl=120)
def get_config(key: str):
    return {"key": key, "value": "some_value"}

# Usage:
# user = await get_user(1)
# config = await get_config("theme")  # Await is required here!
```

If your function takes complex parameters such as `dict`, `list`, ORM objects, request/session objects, or custom class instances, pass `key_builder=...` explicitly. The default key builder raises `TypeError` for unsupported argument types instead of guessing an unstable cache key.

---

## 5. Exceptions and None

- **Exceptions:** Propagate; nothing is written to the cache.
- **None:** `@cached` does not store `None` by default; use `skip_cache_func=lambda r: False` to cache it. `get_or_set` without `skip_cache_func` stores all values (including None via internal sentinel).

---

## 6. RedLock (best-effort)

`get_or_set` uses aiocache RedLock: one producer per key while the lock is held; after `lease` (default 2s) expires, waiters may run producer too. Memory: per-process; Redis: distributed.

---

## 7. Observability

No built-in plugins. For metrics, pass aiocache [Plugins](https://aiocache.aio-libs.org/en/latest/plugins.html) in the same config (e.g. `cache.setup(prefix="myapp", cache="...", plugins=[...])`).

---

## 8. API Reference

### Cache manager and ZodiacCache

::: zodiac_core.cache.manager
    options:
      heading_level: 4
      show_root_heading: true
      members:
        - ZodiacCache
        - CacheManager
        - cache
        - ZODIAC_CACHE_NAMESPACE
        - DEFAULT_CACHE_NAME

### Cached decorator

::: zodiac_core.cache.decorators
    options:
      heading_level: 4
      show_root_heading: true
      members:
        - cached
