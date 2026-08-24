---
name: zodiac-core-integration-summary
description: Produces a ZodiacCore integration matrix for downstream services. Run `zodiac check --format json` for mechanical wiring evidence, then judge pagination, cache, config, schemas, and ➖/❓. Use when the user asks for Zodiac 接入总结、接入矩阵、对接表、zodiac-core 特性对照, a ✅❌ adoption table, or to fix wiring from that report.
---

# ZodiacCore Integration Summary

Use this skill to audit a service that is built with, or is expected to adopt,
ZodiacCore. The output is a compact feature-adoption matrix for developers and
technical leads. Do not rewrite code unless the user explicitly asks for fixes.

## Mechanical wiring via `zodiac check`

The CLI is the source of truth for anti-patterns this skill used to grep for.
Do not re-derive those rules in the prompt.

From the service root:

```bash
uv run zodiac check --format json
```

If the project does not install the CLI extra, or the installed `zodiac-core`
is too old to provide `zodiac check`, stop and prompt the user to upgrade
`zodiac-core` and add `zodiac-core[zodiac]` to dev dependencies (for example
`uv add --dev "zodiac-core[zodiac]"`), then rerun. Do not run the latest CLI
from `uvx` against an older project, and do not re-derive the anti-patterns by
grepping.

If the command exits because the project does not depend on `zodiac-core`,
stop. That is not an adoption matrix.

Map CLI `rules[].rule_id` to matrix columns:

| `rule_id` | Column |
|-----------|--------|
| `routing.*` | Routing & Response |
| `exceptions.*`, `bootstrap.register_exception_handlers` | Exception Handling |
| `bootstrap.register_middleware`, `bootstrap.parent_no_register_middleware`, `bootstrap.subapp_register_middleware` | Middleware |
| `bootstrap.setup_loguru`, `bootstrap.subapp_no_setup_loguru` | Logging |
| `http.*` | HTTP & Upstream |
| `db.*` | Database |
| `layers.*` | Footnote only as an error when present (import-layer anti-pattern, not a table column) |
| `parse.*` / any unlisted `rule_id` | Footnote only; fix the syntax error or check the rule's docs. Do not map an unlisted rule to a column. |

- An **error** on a column that the service is expected to use → ❌. Cite
  `hits[]` and the rule `change` in a footnote.
- A **warning** alone does not flip the cell to ❌ if the service otherwise
  adopts the capability. Footnote it.
- No matching errors, and the service uses the capability → continue with the
  positive-adoption searches below to mark ✅ or ➖.
- `zodiac check` does **not** decide pagination, cache, configuration, or
  schemas. Those columns stay grep + judgment (➖/❓ allowed).
- A green report certifies mechanical wiring only. Session ownership,
  request-derived database names, named resource lifecycle, thin routers, and
  DI still come from the project's `AGENTS.md` and the judgment rules below.

If the user then asks to fix mechanical ❌ cells, apply each error rule's
`change` at `hits[].path`. Use `found` only to locate the code. Re-run
`zodiac check --format json` until `ok` is true, then refresh the matrix.
Do not invent a different fix than `change`. Do not upgrade `zodiac-core` or
rewrite architecture unless asked.

## Status Symbols

| Symbol | Meaning |
|--------|---------|
| ✅ | Adopted: the service actually uses the ZodiacCore capability in code, or declares and uses the relevant optional extra. |
| ❌ | Missing: the service is expected to use the ZodiacCore capability, but the current code does not. |
| ➖ | Not applicable: the capability is intentionally not needed for this service, or a project-specific alternative is acceptable. |
| ❓ | Unknown: the available code is insufficient to decide safely. |

Do not mark custom business pagination as ❌ by default. If the service has an
intentional custom pagination contract and the user did not require ZodiacCore
pagination, mark it as ➖ and explain that in a footnote.

## Output Format

Output one Markdown table row per service. The columns are fixed:

`Service` | `version` | `Routing & Response` | `Exception Handling` | `Middleware` | `Logging` | `HTTP & Upstream` | `Pagination` | `Cache` | `Database` | `Configuration` | `Schemas` | `Sub Applications`

Cells should contain only ✅, ❌, ➖, or ❓. Put explanations below the table as
short footnotes.

Follow the user's language and wording habits for surrounding explanation and
footnotes. Keep the table headers fixed as documented unless the user asks for
a localized table.

Example:

```markdown
| Service | version | Routing & Response | Exception Handling | Middleware | Logging | HTTP & Upstream | Pagination | Cache | Database | Configuration | Schemas | Sub Applications |
|---------|---------|:------------------:|:------------------:|:----------:|:-------:|:---------------:|:----------:|:-----:|:--------:|:-------------:|:-------:|:----------------:|
| example-svc | 0.11.0 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ✅ | ✅ | ✅ | ➖ |

- Pagination is ➖ because this service intentionally keeps a business-specific list contract.
- HTTP & Upstream is ➖ because this service has no downstream HTTP calls.
- Sub Applications is ➖ because this service is a single FastAPI app.
```

## Audit Steps

### 1. Version And Extras

Read `requirements.txt`, `pyproject.toml`, and lock files. Capture the
`zodiac-core` version and extras such as `sql`, `cache`, `mongo`, and `zodiac`.

If the version is older than the current docs, mention that newer features may
not be available. Do not upgrade dependencies unless asked.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/>

### 2. Routing & Response

Prefer `zodiac check` rules `routing.*` for anti-patterns. Then search only
for positive adoption:

- `zodiac_core.routing.APIRouter`
- `ZodiacRoute`
- `zodiac_core.response`
- `response_ok`, `response_created`, `response_not_found`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | Routes use ZodiacCore `APIRouter`, or manual responses use `response_*` helpers, and check has no routing errors. |
| ❌ | Check reports `routing.*` errors, or native FastAPI routing manually constructs JSON responses while the project expects the envelope. |
| ➖ | The service is not a REST JSON API. |
| ❓ | Routing style cannot be confirmed. |

Best practices:

- Prefer `zodiac_core.routing.APIRouter` for routes that should return the
  ZodiacCore response envelope.
- Do not manually wrap every endpoint with `Response(data=...)`; let
  `ZodiacRoute` do it.
- Return FastAPI response objects directly for files, redirects, streaming, or
  other non-envelope responses.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/routing/>

### 3. Exception Handling

Prefer `zodiac check` rules `exceptions.*` and
`bootstrap.register_exception_handlers`. Then search for:

- `register_exception_handlers`
- `ZodiacException`
- `BadRequestException`, `NotFoundException`, `ForbiddenException`
- `UpstreamServiceException`, `UpstreamRequestException`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The app calls `register_exception_handlers(app)`, business code uses ZodiacCore exceptions, and check has no exception/bootstrap handler errors. |
| ❌ | Check reports exception or handler errors, or the app uses bare `HTTPException` / hand-written JSON errors where ZodiacCore exceptions are expected. |
| ➖ | The service intentionally owns a different exception system. |
| ❓ | Handlers or business exception usage cannot be confirmed. |

Best practices:

- Register exception handlers once on each FastAPI app that owns routes.
- Use built-in ZodiacCore exceptions for standard business errors.
- Use `translate_upstream_errors` for downstream HTTP failures.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/exceptions/>

### 4. Middleware

Prefer `zodiac check` middleware bootstrap rules. Then search for:

- `register_middleware`
- `TraceIDMiddleware`
- `AccessLogMiddleware`
- `ServiceNameMiddleware`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service uses `register_middleware(app)` or correctly installs Trace ID and access log middleware, and check has no middleware bootstrap errors. |
| ❌ | Check reports middleware bootstrap errors, or an HTTP service lacks tracing/access logging while the project expects ZodiacCore observability. |
| ➖ | The project is a CLI, job, or non-ASGI process. |
| ❓ | Middleware exists but its ownership or implementation is unclear. |

Best practices:

- Use `register_middleware(app, service_name="...")` for ordinary services.
- For mounted sub-applications, register middleware on the sub-apps that own
  the routes to avoid duplicate access logs.
- Use `exclude_paths` for noisy health checks when appropriate.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/middleware/>

### 5. Logging

Prefer `zodiac check` logging bootstrap rules. Then search for:

- `setup_loguru`
- `from loguru import logger`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service configures logging with `setup_loguru(...)` and check has no logging bootstrap errors. |
| ❌ | Check reports logging bootstrap errors, or the service uses raw logging setup where ZodiacCore JSON logs are expected. |
| ➖ | The project is not a long-running service process. |
| ❓ | Logging setup cannot be located. |

Best practices:

- Call `setup_loguru()` once in the process entry point.
- Use `json_format=True` in production.
- Use `service_name` as the default log service label; middleware service names
  override it for request-scoped logs.
- Application code can import `logger` from Loguru directly after setup.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/logging/>

### 6. HTTP & Upstream

Prefer `zodiac check` rules `http.*` for raw clients. Then search for:

- `ZodiacClient`
- `ZodiacSyncClient`
- `init_http_client`
- `translate_upstream_errors`
- raw `httpx`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | Downstream HTTP calls use `ZodiacClient` or `ZodiacSyncClient`, upstream errors are translated when needed, and check has no `http.*` errors. |
| ❌ | Check reports `http.*` errors, or the service uses raw `httpx` without trace propagation or error translation where required. |
| ➖ | The service has no downstream HTTP calls. |
| ❓ | HTTP client usage is present but cannot be classified. |

Best practices:

- Use `ZodiacClient` for automatic request ID propagation.
- Use `@translate_upstream_errors(service="...")` around downstream calls and
  call `response.raise_for_status()` inside the decorated function.
- Manage shared clients with `init_http_client()` in application lifecycle or DI.

Docs:

- <https://ttwshell.github.io/ZodiacCore-Py/latest/api/context/>
- <https://ttwshell.github.io/ZodiacCore-Py/latest/api/exceptions/#4-upstream-service-errors>

### 7. Pagination

Search for:

- `PageParams`
- `PageSortParams`
- `PagedResponse`
- `SortSpec`
- `paginate`
- `paginate_query`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | List APIs use ZodiacCore pagination parameters/responses and repository pagination helpers. |
| ❌ | The project requires ZodiacCore pagination but list APIs are hand-written without it. |
| ➖ | There are no list APIs, or custom pagination is intentional and accepted. |
| ❓ | List API or repository implementation cannot be confirmed. |

Best practices:

- Use `Annotated[PageParams, Query()]` or `Annotated[PageSortParams, Query()]`
  at the route boundary.
- Use `SortSpec` to whitelist sortable fields.
- Use `paginate_query()` for repository-owned session management.
- Return `PagedResponse[Schema]` for list responses.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/pagination/>

### 8. Cache

Search for:

- `zodiac-core[cache]`
- `cache.setup`
- `@cached`
- `get_or_set`
- `get_cache`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service declares the `cache` extra, sets up cache lifecycle, and uses cache APIs. |
| ❌ | The service declares or requires cache support but never sets up or uses ZodiacCore cache. |
| ➖ | The service has no cache requirement. |
| ❓ | Cache setup exists but runtime usage is unclear. |

Best practices:

- Call `cache.setup(prefix="...", default_ttl=...)` during startup.
- Call `await cache.shutdown()` during shutdown; use `name` for scoped shutdown.
- Use explicit key builders for complex arguments.
- Remember `@cached` always returns an async wrapper.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/cache/>

### 9. Database

Prefer `zodiac check` rules `db.*` for session anti-patterns. Then search for:

- `zodiac-core[sql]`
- `db.setup`
- `BaseSQLRepository`
- `get_session`
- `session_dependency`
- `db.session`
- `init_db_resource`
- `IntIDModel`, `UUIDModel`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service uses ZodiacCore database setup, repositories, and SQLModel bases, and check has no `db.*` errors. |
| ❌ | Check reports `db.*` errors, or the service has SQL operations but bypasses ZodiacCore where the project standard requires it. |
| ➖ | The service has no SQL database. |
| ❓ | Database usage cannot be classified. |

Best practices:

- Initialize `db.setup(...)` in application lifecycle.
- Explicitly `await session.commit()`; sessions do not auto-commit.
- Use named databases only when a service truly needs more than one DB.
- Do not add a route session dependency merely because a route eventually
  calls a repository. `BaseSQLRepository` already owns its sessions by
  default. Only when the route deliberately owns a shared unit of work or
  performs database work directly, use `Depends(get_session)` for the default
  database or bind a named database once at module or router scope with
  `get_analytics_session = session_dependency("analytics")` and pass that
  stored zero-argument callable to `Depends`.
- Treat database names as trusted application wiring. Never derive them from
  query, path, header, body, or other request data.
- Treat a server-controlled `get_session(name)` call inside an existing
  zero-argument wrapper dependency as source-compatible behavior. Do not break
  it merely because it is old; recommend migrating touched routes and writing
  new named route wiring with `session_dependency(name)` so FastAPI directly
  manages rollback and cleanup.
- `partial(get_session, ...)` and `Depends(session_dependency)` (including
  `Depends(db.session_dependency)`) are mechanical errors. Prefer the
  `zodiac check` `db.*` rules over grepping. The `change` field is the fix.
- FastAPI dependencies are API/DI-boundary APIs, not general-purpose session
  APIs. Lower layers must never call dependency callables. If the API owns the
  unit of work, pass the concrete injected `AsyncSession` to participating
  services and repositories. Otherwise preserve repository-owned
  `self.session()` or use `db.session(name)` in the service, job, CLI command,
  startup task, or other unit-of-work owner.
- By default, FastAPI creates one `AsyncSession` per stored dependency callable
  per request; repeated uses of the callable in that request share the session,
  and a later request gets a new one. Every `db.session(...)` context creates
  its own session. Engines and pools are shared per registered database name.
  Never share a session across requests or concurrent tasks.
- Use Alembic for production migrations; keep `db.create_all()` for development
  or generated-project smoke tests.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/db/>

### 10. Configuration

Search for:

- `ConfigManagement`
- `get_config_files`
- `provide_config`
- `StrictConfig`
- `strtobool`
- `providers.Configuration(strict=True)`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service loads `.ini` config through `ConfigManagement` and validates sections with `StrictConfig`. |
| ❌ | Configuration is scattered or hardcoded where project standards require ZodiacCore config handling. |
| ➖ | The project has only trivial configuration and intentionally uses environment variables directly. |
| ❓ | Config loading path cannot be confirmed. |

Best practices:

- Use `providers.Configuration(strict=True)`.
- Load files with `from_ini(path, required=True)`.
- Model config sections with `StrictConfig`.
- Prefer `ConfigManagement.provide_config(container.config.db(), DbConfig)` for
  section-level conversion and validation.
- Do not use `as_(bool)` for INI booleans; use `strtobool` or Pydantic models.
- Tests should run with `APPLICATION_ENVIRONMENT=testing` and `app.testing.ini`
  when the project has environment-specific config.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/config/>

### 11. Schemas

Search for:

- `CoreModel`
- `IntIDSchema`
- `UUIDSchema`
- `UtcDatetime`
- `DateTimeSchemaMixin`
- raw `BaseModel`
- `ConfigDict(from_attributes=True)`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | API schemas use ZodiacCore schema bases and datetime helpers. |
| ❌ | Schemas use raw Pydantic bases and repeat config that ZodiacCore already provides. |
| ➖ | The service has no Pydantic API schemas. |
| ❓ | Schema usage cannot be confirmed. |

Best practices:

- Use `CoreModel` for ordinary request/response schemas.
- Use `IntIDSchema` or `UUIDSchema` for DB-backed read models.
- Use `UtcDatetime` for datetime fields that should normalize to UTC.
- Do not repeat `ConfigDict(from_attributes=True)` when inheriting from
  ZodiacCore schema bases.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/api/schemas/>

### 12. Sub Applications

Prefer `zodiac check` middleware/logging bootstrap rules for duplicate
middleware and misplaced `setup_loguru`. Lifespan order, mount paths, and
named shutdown still need reading `main.py`. Search for:

- `app.mount(`
- `FastAPI(lifespan=`
- `router.lifespan_context`
- `create_users_app`, `create_orders_app`, or other `create_*_app` factories
- parent-only health routes such as `/api/health`
- sub-app middleware registration such as `register_middleware(app, service_name=...)`

Mark:

| Symbol | Condition |
|--------|-----------|
| ✅ | The service uses mounted FastAPI sub-applications with clear parent/sub-app ownership, scoped middleware/logging, explicit sub-app lifespan entry when needed, and correct shared resource lifecycle. |
| ❌ | The service mounts sub-applications but has unsafe lifecycle, duplicated middleware/access logs, unclear service log attribution, or shared resource shutdown risks. |
| ➖ | The service is a single FastAPI app or does not use `app.mount()`. |
| ❓ | The service appears to mount apps, but parent/sub-app lifecycle or middleware ownership cannot be confirmed. |

Best practices:

- Parent app owns process-wide setup such as `setup_loguru()`, shared database,
  shared cache, and parent-only routes like `/api/health`.
- Sub-applications own their routers, schemas, services, repositories, DI
  containers, exception handlers, and request middleware.
- Do not register normal request middleware on both the parent and mounted
  sub-apps for the same request path; this causes duplicate request IDs and
  duplicate access logs.
- Use `register_middleware(sub_app, service_name="...")` so each sub-app gets
  correct request-scoped log attribution.
- If sub-apps define lifespan logic, the parent lifespan must explicitly enter
  each sub-app lifespan with `sub_app.router.lifespan_context(sub_app)`.
- Initialize parent-owned shared database/cache before entering sub-app
  lifespans, so sub-apps start after and stop before shared resources.
- Use `db.shutdown(name="...")` and `cache.shutdown(name="...")` for scoped
  sub-app-owned resources. Bare shutdown closes all registered resources.
- Parent OpenAPI docs normally show parent routes only; mounted sub-app docs
  live under each mount unless the project intentionally aggregates docs.

Docs: <https://ttwshell.github.io/ZodiacCore-Py/latest/user-guide/sub-applications/>

## Footnote Rules

- Add at least one footnote for each ➖ or ❓ column.
- For ❌, explain the missing API or missing call site. For mechanical
  wiring ❌, cite the `zodiac check` `rule_id` and `change`.
- If the service uses an older ZodiacCore version, mention that newer features
  may not exist in that version.
- Keep footnotes short. Prefer one to three high-signal notes.
