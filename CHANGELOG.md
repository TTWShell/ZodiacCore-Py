# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).



## [0.5.2] - 2026-03-09

### Fixed

- **HTTP**: Use `HTTP_422_UNPROCESSABLE_CONTENT` (RFC 9110) instead of deprecated `HTTP_422_UNPROCESSABLE_ENTITY` in `UnprocessableEntityException` and `response_unprocessable_entity()`, resolving Starlette deprecation warnings.

### Changed

- **Dependencies**: Require `starlette>=0.48.0` so the RFC 9110 status constant is available.

## [0.5.1] - 2026-03-06

### Added

- **Cache**: Support for synchronous functions in the `@cached` decorator. The decorated function becomes asynchronous and must be awaited by the caller, allowing cache reuse for both async and sync business logic.
- **Template**: Integrated cache support into the `standard-3tier` project template, including optional dependency, configuration, initialization in `main.py`, and README usage notes.
- **Tests**: Test cases for sync function support in the `@cached` decorator.

### Changed

- **Docs**: Cache API docs clarify that `@cached` supports both async and sync functions; add usage examples and note that caller must always await.

## [0.5.0] - 2026-03-04

### Added

- **Cache**: Unified cache layer on aiocache (optional extra `zodiac-core[cache]`). `CacheManager` singleton with `setup(prefix, ...)` / `get_cache(name)` / `shutdown()`; `ZodiacCache` with `get` / `set` / `delete` / `exists` and `get_or_set` (RedLock stampede protection, optional `skip_cache_func`). `@cached(ttl, key_builder, name, skip_cache_func)` decorator for async functions; default key builder hashes fn + args (pickle with repr fallback for unpicklable args). Namespace `zodiac_cache:{prefix}`; multi-cache via `name` parameter.
- **Docs**: Cache API documentation (`docs/api/cache.md`) for setup, decorator, get_or_set, and named caches.
- **Tests**: Cache test suite (decorator key/name/skip_cache_func, manager setup/get_cache/shutdown, ZodiacCache get_or_set/RedLock/skip_cache_func); integration test for optional `[cache]` extra.

## [0.4.0] - 2026-03-03

### Added

- **Middleware**: WebSocket support for `TraceIDMiddleware` and `AccessLogMiddleware`. Request ID is read from the WebSocket upgrade request headers (or generated), set in context for the connection lifetime, and reset on close. Access log records `WEBSOCKET {path} - 101 - {latency}ms`. Lifespan scope is passed through without request_id or access log.
- **Context**: `request_id_scope(request_id)` context manager to set and reset request ID on exit (used internally by middleware; available for custom ASGI apps that need the same semantics).

### Changed

- **Middleware**: Replace `BaseHTTPMiddleware` with Pure ASGI implementation for `TraceIDMiddleware` and `AccessLogMiddleware`. Request handling uses `scope` / `receive` / `send` directly, improving latency and stability under load. Module docstring links to ASGI spec for scope types (`http`, `websocket`, `lifespan`).
- **Makefile**: `make bench-compare` supports an optional run ID (e.g. `make bench-compare ID=0002`); default remains `0001`.
- **Docs**: Clarify uv usage and scaffold flow in installation and getting-started; reduce redundancy in CLI and scaffold docs.
- **Template**: Use async httpx client in standard-3tier generated tests.

### Other

- **Tests**: Add middleware tests for WebSocket and lifespan behavior; add coverage for response helpers, HTTP client hooks, and schemas `ensure_utc`.

## [0.3.0] - 2026-02-25

### Added

- **Exceptions**: `UnprocessableEntityException` (HTTP 422) for business/semantic validation errors when the request is well-formed but not processable. Exception definitions, handlers, exports, and docs are ordered by HTTP status code (400–422).
- **CI & coverage**: Upload coverage reports to Codecov in CI and enable XML coverage reports (`--cov-report=xml`) for tooling integration.
- **Database tests**: Add an async integration test for `DatabaseManager.verify()` to ensure database connectivity can be checked reliably.

### Changed

- **README**: Replace badge layout with concise shields, adding direct links to documentation, PyPI, and Codecov status.
- **Tooling**: Update ignore rules to keep generated coverage artifacts (`coverage.xml`) out of version control, while keeping docs changelog managed through the docs site.

## [0.2.1] - 2026-02-11

### Fixed

- **Dependency Isolation**: Fixed an issue where `zodiac_core.db` submodules forced `sqlalchemy` imports. Now optionally loads and provides clear installation guidance when `zodiac-core[sql]` is missing.

## [0.2.0] - 2026-02-06

### Added

- **zodiac CLI**: `zodiac new PROJECT_NAME --tpl standard-3tier -o OUTPUT_DIR` to scaffold projects (optional extra `zodiac-core[zodiac]`).
- **standard-3tier template**: Full FastAPI project with 3-tier architecture (API / Application / Infrastructure), dependency-injector, file-based config (`.ini`), and `Container.initialize()` that auto-wires all `*_router` modules.
- **Config**: `ConfigManagement.provide_config(config, model)` — optional Pydantic model for type-safe, validated config (backward compatible with SimpleNamespace).
- **Database**: `BaseSQLRepository.paginate()` and `paginate_query()` for standardized pagination with count and optional schema transformation.
- **Documentation**: Architecture guide (layered design, DI, wiring), CLI guide, pagination API (repository methods), and getting-started aligned with template.


## [0.1.0] - 2026-02-02

### Added

- **Routing**: `ZodiacAPIRouter` with automatic `Response[T]` wrapping using Pydantic v2 native generics
- **Response**: Standard API response model `Response[T]` with `code`, `data`, `message` fields
- **Exceptions**: `ZodiacException` hierarchy (`NotFoundException`, `BadRequestException`, `ForbiddenException`, `UnauthorizedException`, `ConflictException`)
- **Exception Handlers**: Centralized handlers for `ZodiacException`, `RequestValidationError`, and generic exceptions
- **Middleware**: `TraceIDMiddleware` for request tracing, `AccessLogMiddleware` for structured access logging
- **Logging**: `setup_loguru()` with JSON format support and Trace ID injection
- **Context**: `trace_id` context variable for cross-cutting request tracing
- **Config**: `BaseAppSettings` with environment-based configuration using Pydantic Settings
- **Database**:
  - `DatabaseManager` singleton for async SQLAlchemy engine/session management
  - `BaseSQLRepository` with session context manager
  - SQLModel mixins: `IntIDMixin`, `UUIDMixin`, `SQLDateTimeMixin`
- **HTTP**: `HttpClient` async wrapper around httpx with automatic Trace ID propagation
- **Pagination**: `PageParams` request model and `PagedResponse[T]` response model
- **Schemas**: Pydantic mixins: `IntIDSchemaMixin`, `UUIDSchemaMixin`, `DateTimeSchemaMixin`
- **Benchmarks**: Performance benchmarks for routing overhead and internal operations
- **Documentation**: MkDocs-based API reference and user guide
