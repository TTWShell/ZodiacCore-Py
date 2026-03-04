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

**@cached:** Key from `module:qualname:hash(args,kwargs)`. Uses default cache; pass `name="other"` to use `cache.get_cache("other")`.

```python
from zodiac_core.cache import cache, cached

cache.setup(prefix="myapp", default_ttl=300)

@cached(ttl=60)
async def get_user(user_id: int):
    return await db.fetch_user(user_id)
```

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
