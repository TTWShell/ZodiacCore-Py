# Cache (Unified Layer)

Unified cache on **aiocache**: one-time `cache.setup`, global default cache, stampede-protected `get_or_set` and `@cached`.

## 1. Core concepts

- **cache** (CacheManager): singleton; `cache.setup(prefix=...)` once, then `cache.cache` (or `cache.get_cache(name)`) and `@cached` use it.
- **ZodiacCache**: thin wrapper over aiocache `BaseCache` — `get` / `set` / `delete` / `exists` and **get_or_set** (RedLock stampede protection).
- **Namespace**: `cache.setup(prefix="...")` → keys under `zodiac_cache:{prefix}`.
- **Lifecycle**: `await cache.shutdown(name="...")` releases one named cache; `await cache.shutdown()` releases all registered caches.

---

## 2. Installation

```bash
pip install 'zodiac-core[cache]'
```

Requires `aiocache>=0.12.0`. For Redis etc., see [aiocache docs](https://aiocache.aio-libs.org/en/latest/).

---

## 3. Configuration

Call `cache.setup` at startup; optionally `await cache.shutdown()` on shutdown.
Calling `cache.setup(...)` again with the same `name` is allowed only when the effective configuration is identical; different settings for an existing name raise `RuntimeError`.
Lifecycle control is **name-aware**:

- `await cache.shutdown(name="...")` closes only the selected named cache.
- `await cache.shutdown()` closes all registered caches.

This preserves the singleton manager design for shared cache backends while letting each app or resource release only the cache it owns.

### In-memory (default)

Pass only `prefix` (and optional `default_ttl`). We set default `cache` and `serializer`; namespace is always `zodiac_cache:{prefix}`.

```python
from zodiac_core.cache import cache

cache.setup(prefix="myapp", default_ttl=300)
```

### Custom backend (Redis, etc.)

Use aiocache's same parameters as `caches.add()`. We only inject/override `namespace` and minimal defaults.

```python
from zodiac_core.cache import cache


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

When cleaning up, pair named setup with named shutdown:

```python
from zodiac_core.cache import cache


async def shutdown_named_caches() -> None:
    cache.setup(prefix="myapp", default_ttl=300)
    cache.setup(
        prefix="sessions",
        name="sessions",
        cache="aiocache.RedisCache",
        endpoint="127.0.0.1",
    )

    await cache.shutdown(name="sessions")  # only the sessions cache
    await cache.shutdown()  # full cleanup
```

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

For a single-app service, `await cache.shutdown()` remains the simplest option.
If your process registers multiple named caches or shares the global manager across multiple app lifecycles, prefer `await cache.shutdown(name="...")` for scoped cleanup.

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
    return {"user_id": user_id}

# Sync function (now supported, but caller MUST await)
@cached(ttl=120)
def get_config(key: str):
    return {"key": key, "value": "some_value"}

# Usage:
# user = await get_user(1)
# config = await get_config("theme")  # Await is required here!
```

If your function takes complex parameters such as `dict`, `list`, ORM objects, request/session objects, or custom class instances, pass `key_builder=...` explicitly. The default key builder raises `TypeError` for unsupported argument types instead of guessing an unstable cache key.

### Receiver-aware default keys

`@cached` also supports receiver-aware default keys for methods:

- `include_cls=True`: For class methods, add the bound class identity (`cls.__module__` + `cls.__qualname__`) to the default cache key.
- `include_self=True`: For instance methods, add the receiver class identity (`self.__class__.__module__` + `self.__class__.__qualname__`) to the default cache key.

This feature relies on the conventional first parameter names `cls` and `self`.
If you use non-standard receiver names, provide a custom `key_builder`.

Place `@cached(...)` closest to the function definition. For class methods, use `@classmethod` above `@cached(...)`.

> **Important**
>
> `include_cls=True` is appropriate only when the cache should vary by the bound class.
> In inheritance-heavy code, enabling it means parent and child classes will use different cache keys even when they call the same method implementation.

> **Warning**
>
> `include_self=True` is **class-scoped**, not instance-scoped.
> It is intended for singleton services or functionally equivalent instances of the same class.
> If instance-specific configuration affects the result, do **not** rely on `include_self=True`; provide a custom `key_builder` instead.

```python
from zodiac_core.cache import cached


class UserService:
    @cached(ttl=60, include_self=True)
    async def get_user(self, user_id: int):
        return await self.repo.get(user_id)


class UserSchema:
    @classmethod
    @cached(ttl=60, include_cls=True)
    async def resolve(cls, key: str):
        return f"{cls.__name__}:{key}"
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
