# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
