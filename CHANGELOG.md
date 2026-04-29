# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-04-29

### Added

- **HTTP**: Add `translate_upstream_errors(service)` to convert `httpx` upstream status and request failures into standardized ZodiacCore exceptions for both async and sync functions.
- **Exceptions**: Add `UpstreamServiceException` and `UpstreamRequestException` for explicit upstream service failures, including service name and upstream error classification.
- **Exception Handlers**: Register a dedicated upstream exception handler that returns standardized HTTP 400 responses for translated upstream failures.
- **Templates**: Update the `standard-3tier` external client example to use `ZodiacClient` with `translate_upstream_errors`.
- **Docs**: Document upstream error translation, manual upstream business-error mapping, and the new upstream exception types in the exceptions API guide.
- **Tests**: Add coverage for upstream exception behavior, handler registration, async/sync HTTP translation, and template usage.

## [0.8.1] - 2026-04-26

### Fixed

- **Exceptions**: Respect `http_code` declared on direct `ZodiacException` subclasses when converting them to HTTP responses, while preserving fixed HTTP statuses for built-in exception families.

### Changed

- **Docs**: Clarify the distinction between HTTP status codes and business error codes, including how built-in exception families and direct `ZodiacException` subclasses should be used.

## [0.8.0] - 2026-04-14

### Added

- **CLI**: `--package-name` option for `zodiac new` command to customize the generated Python package name (defaults to `app`).
- **Middleware**: `ServiceNameMiddleware` for scoping service names in request context, allowing per-app log attribution in multi-app deployments.
- **Context**: `service_name_scope` and `get_service_name` for managing service-level context in `zodiac_core.context`.
- **Logging**: Loguru patcher now prefers `service_name` from context if available, enabling accurate service tagging in shared logging sinks.
- **Templates**: `standard-3tier` template now fully supports dynamic package names and includes `ServiceNameMiddleware` registration by default.
- **Tests**: Comprehensive multi-app integration tests (`tests/multi_app/dual_full_apps/`) using real Uvicorn servers to validate isolation and shared resources.

### Changed

- **CLI**: `zodiac new` now validates package names against Python identifiers and reserved names (`main`, `config`, `tests`).
- **Middleware**: `register_middleware` now accepts an optional `service_name` to automatically enable `ServiceNameMiddleware`.
- **Docs**: Documentation updated with `--package-name` usage and architectural details for multi-app setups.

## [0.7.0] - 2026-03-31

### Added

- **Database**: `get_session()` accepts an optional `name` parameter for multi-database support; defaults to the default database for backward compatibility.
- **Config**: `StrictConfig` base model (`extra='forbid'`, `frozen=True`) for configuration section Pydantic models — rejects typo keys and prevents mutation after creation.
- **Utils**: `strtobool()` as a Python 3.13+ compatible drop-in replacement for the removed `distutils.util.strtobool`, returning `bool` instead of `int`.
- **Docs**: Best practices guide for `dependency-injector` Configuration (strict mode, required files, type conversion pitfalls, environment variable interpolation).
- **Docs**: API reference page for the `zodiac_core.utils` module.
- **Tests**: Integration tests for `dependency-injector` `strict=True` + `required=True` + `as_(strtobool)` and `StrictConfig` constraints; `dependency-injector` added as dev dependency.

### Changed

- **Template**: Generated projects use `providers.Configuration(strict=True)` and `from_ini(path, required=True)` for fail-fast configuration loading.
- **Template**: Config models (`DbConfig`, `CacheConfig`) inherit `StrictConfig` instead of `BaseModel`; type conversion uses Pydantic models via `ConfigManagement.provide_config()` instead of manual `as_()` calls.
- **Docs**: All code examples across config, context, architecture, and getting-started guides updated to use `strict=True`, `required=True`, and `strtobool` imports from `zodiac_core.utils`.

### Fixed

- **Config**: Replace `as_(bool)` / `as_=bool` with `as_(strtobool)` for boolean config values — `bool("false")` evaluates to `True`, causing silent misconfiguration.
- **Tests**: Force reinstall `zodiac-core` in generated project quality test to prevent stale `uv` cache from masking template breakage.

## [0.6.1] - 2026-03-27

### Added

- **Cache**: Optional `include_cls` and `include_self` on `@cached` so the default key builder can fold receiver **class** identity into the key for `classmethod`s (`cls`) and instance methods (`self`), gated by conventional first-parameter names; document that `include_self` is class-scoped (not per-instance) and that inheritance changes cache partitioning when enabled.
- **Tests**: Expand `@cached` coverage for custom `key_builder`, `include_cls` with base/derived classes, `include_self` sharing across instances of the same class, parent/child class separation, and instance methods that still require an explicit `key_builder` when receiver-aware keys are omitted.

### Changed

- **Docs**: Add a “Receiver-aware default keys” section to the cache API guide (constraints, warnings, and examples for class vs instance methods).

## [0.6.0] - 2026-03-26

### Added

- **HTTP**: Add `init_http_client()` as a lifecycle helper for creating and closing a shared `ZodiacClient` within an application or DI resource.
- **Database**: Add scoped shutdown support via `db.shutdown(name="...")` so a single named database can be released without disposing all registered engines.
- **Cache**: Add scoped shutdown support via `cache.shutdown(name="...")` so a single named cache can be released without clearing all registered caches.
- **Tests**: Add coverage for named database/cache shutdown and for `init_db_resource()` cleaning up only its own database name.

### Changed

- **Database**: Make `DatabaseManager.setup()` deterministic by allowing repeated setup only for the same effective configuration and raising `RuntimeError` for conflicting configuration on an existing name.
- **Database**: Make `init_db_resource()` release only the database registered under its own `name`, preserving other shared database resources in the same process.
- **Template**: Manage the shared HTTP client as an application resource in the standard 3-tier template and initialize app resources through `AsyncExitStack`.
- **Template**: Align generated project configuration loading with `APPLICATION_ENVIRONMENT` and default the template fallback environment to `develop`.
- **CLI**: Clarify that `zodiac new --force` allows generation into an existing directory without removing unrelated files.
- **Docs**: Update database, cache, config, context, architecture, CLI, and getting-started documentation to reflect the scoped resource lifecycle and template conventions.

### Fixed

- **Template**: Ensure generated projects use resource lifecycle management for shared HTTP clients instead of relying on unmanaged singleton client instances.

## [0.5.4] - 2026-03-23

### Changed

- **Cache**: Restrict the default `@cached` key builder to stable immutable parameters and require an explicit `key_builder` for complex arguments instead of falling back to unstable automatic keys.
- **Cache**: Make `cache.setup(...)` deterministic by allowing repeated setup only for identical effective configuration and raising `RuntimeError` for conflicting settings.
- **Docs**: Clarify cache setup idempotency rules and document the supported/default key-builder constraints for `@cached`.

### Fixed

- **Cache**: Decode the internal cached-`None` sentinel in public `get()` while preserving correct `get_or_set()` hit detection under lock rechecks.
- **Cache**: Preserve `default_ttl` when rebuilding a `ZodiacCache` wrapper from an existing aiocache alias.

### Added

- **Tests**: Expand cache coverage for tuple-based default keys, deterministic setup behavior, wrapper rebuild state, public `get()` after cached `None`, and the cached-`None` lock recheck path.

## [0.5.3] - 2026-03-17

### Fixed

- **Logging**: When `json_format=True`, use empty `"text"` in serialized JSON so the message appears only in `record.message`, avoiding duplication and reducing log size (loguru#594).

### Changed

- **Logging**: Unify console and file sink defaults in `setup_loguru()` via shared `_sink_defaults` and `_apply_sink_defaults()`; document empty-text behavior and override via `console_options`/`file_options` in docstring.

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
