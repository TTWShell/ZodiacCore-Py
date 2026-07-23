# ZodiacCore Source Map

Use this map after resolving the user's ZodiacCore version. Documentation
describes intended usage, public source defines signatures and defaults, tests
show observable contracts, and templates show generated output.

| Topic | Documentation | Source or templates | Focused tests and search terms |
|---|---|---|---|
| Installation and extras | `docs/user-guide/installation.md`, `docs/user-guide/getting-started.md` | `pyproject.toml`, `zodiac_core/__init__.py` | `tests/test_integration_install.py`; `project.optional-dependencies` |
| Configuration and environments | `docs/api/config.md` | `zodiac_core/config.py` | `tests/test_config.py`; `load_config`, `APPLICATION_ENVIRONMENT` |
| Request context and HTTP clients | `docs/api/context.md` | `zodiac_core/context.py`, `zodiac_core/http.py` | `tests/test_http.py`, `tests/test_middleware.py`; `request_id`, `ZodiacClient` |
| Cache and `@cached` | `docs/api/cache.md` | `zodiac_core/cache/decorators.py`, `zodiac_core/cache/manager.py` | `tests/cache/test_cached.py`, `tests/cache/test_manager.py`; `lease`, `include_self`, `key_builder` |
| Database and repositories | `docs/api/db.md` | `zodiac_core/db/` | `tests/db/`; `DatabaseManager`, `Repository`, `paginate_query` |
| Exceptions and upstream errors | `docs/api/exceptions.md` | `zodiac_core/exceptions.py`, `zodiac_core/exception_handlers.py` | `tests/test_exceptions.py`, `tests/test_exception_handlers.py`; `translate_upstream_errors` |
| Logging | `docs/api/logging.md` | `zodiac_core/logging.py` | `tests/test_logging.py`; `setup_loguru`, `json_format`, `exception` |
| Middleware | `docs/api/middleware.md` | `zodiac_core/middleware.py` | `tests/test_middleware.py`, `tests/multi_app/`; `register_middleware`, `exclude_paths` |
| Pagination | `docs/api/pagination.md` | `zodiac_core/pagination.py`, `zodiac_core/db/repository.py` | `tests/test_pagination.py`, `tests/db/test_repository_pagination.py` |
| Routing and response envelopes | `docs/api/routing.md` | `zodiac_core/routing.py`, `zodiac_core/response.py` | `tests/test_routing.py`, `tests/test_response.py`; `APIRouter`, `ZodiacRoute` |
| Shared schemas and utilities | `docs/api/schemas.md`, `docs/api/utils.md` | `zodiac_core/schemas.py`, `zodiac_core/utils.py` | `tests/test_schemas.py`, `tests/test_utils.py` |
| Architecture | `docs/user-guide/architecture.md` | `zodiac_core/`, `zodiac/templates/` | Search the relevant component tests |
| CLI and project generation | `docs/user-guide/cli.md` | `zodiac/main.py`, `zodiac/commands/` | `tests/zodiac/`; `new`, `add sub-app`, rendering plan |
| Sub-applications | `docs/user-guide/sub-applications.md` | `zodiac/templates/sub-applications/`, `zodiac/templates/sub-app/` | generated-project cases in `tests/zodiac/`, `tests/multi_app/` |
| Standard three-tier template | `docs/user-guide/getting-started.md` | `zodiac/templates/standard-3tier/` | `tests/test_build.py`, `tests/zodiac/test_rendering.py` |
| Releases and migrations | `CHANGELOG.md`, versioned docs | Git tags and diffs | Search changed public symbols and their focused tests |

For a published release without a local checkout, replace local documentation
paths with:

```text
https://ttwshell.github.io/ZodiacCore-Py/<version>/
https://github.com/TTWShell/ZodiacCore-Py/tree/<version>/
```

Do not use a GitHub `master` source URL as evidence for an older version.
