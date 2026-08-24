"""High-confidence ZodiacCore wiring rules."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from zodiac.check.models import Finding, Severity
from zodiac.check.module import FunctionNode, ModuleView
from zodiac.check.project import LAYOUT_STANDARD, LAYOUT_SUB_APPLICATIONS, Project

DOCS = "https://ttwshell.github.io/ZodiacCore-Py/latest"
FASTAPI_APP = "fastapi.FastAPI"
SETUP_LOGURU = frozenset(
    {
        "zodiac_core.logging.setup_loguru",
        "zodiac_core.setup_loguru",
    }
)
REGISTER_HANDLERS = frozenset(
    {
        "zodiac_core.exception_handlers.register_exception_handlers",
        "zodiac_core.register_exception_handlers",
    }
)
REGISTER_MIDDLEWARE = frozenset(
    {
        "zodiac_core.middleware.register_middleware",
        "zodiac_core.register_middleware",
    }
)
FASTAPI_API_ROUTERS = frozenset({"fastapi.APIRouter", "fastapi.routing.APIRouter"})
HTTP_EXCEPTIONS = frozenset(
    {
        "fastapi.HTTPException",
        "fastapi.exceptions.HTTPException",
        "starlette.exceptions.HTTPException",
    }
)
GET_SESSION = frozenset({"zodiac_core.db.get_session", "zodiac_core.db.session.get_session"})
SESSION_DEPENDENCY = frozenset(
    {
        "zodiac_core.db.session_dependency",
        "zodiac_core.db.session.session_dependency",
    }
)
HTTPX_CLIENTS = frozenset({"httpx.AsyncClient", "httpx.Client"})
HTTPX_SHORTCUTS = frozenset(
    {
        "httpx.get",
        "httpx.post",
        "httpx.put",
        "httpx.patch",
        "httpx.delete",
        "httpx.request",
        "httpx.stream",
    }
)
RuleFn = Callable[[ModuleView], list[Finding]]


class Rule:
    """Shared contract text for one check."""

    def __init__(
        self,
        rule_id: str,
        contract: str,
        change: str,
        docs: str,
        severity: Severity = "error",
    ) -> None:
        self.rule_id = rule_id
        self.severity = severity
        self.contract = contract
        self.change = change
        self.docs = f"{DOCS}{docs}"

    def finding(
        self,
        *,
        path: Path,
        line: int = 1,
        column: int = 1,
        found: str = "",
        change: str | None = None,
    ) -> Finding:
        return Finding(
            rule_id=self.rule_id,
            severity=self.severity,
            path=path,
            line=line,
            column=column,
            found=found,
            contract=self.contract,
            change=change or self.change,
            docs=self.docs,
        )

    def hit(
        self,
        module: ModuleView,
        node: ast.AST | None = None,
        *,
        line: int | None = None,
        column: int | None = None,
        found: str | None = None,
        change: str | None = None,
    ) -> Finding:
        if node is not None:
            if line is None:
                line = getattr(node, "lineno", 1)
            if column is None:
                column = getattr(node, "col_offset", 0) + 1
            if found is None:
                found = module.source_line(node)
        return self.finding(
            path=module.rel_path,
            line=1 if line is None else line,
            column=1 if column is None else column,
            found=found or "",
            change=change,
        )


PARSE_ERROR = Rule(
    "parse.syntax_error",
    "Contract files must be valid Python so `zodiac check` can verify them.",
    "Fix the syntax error, then rerun `zodiac check`.",
    "/user-guide/cli/",
)
USE_ZODIAC_API_ROUTER = Rule(
    "routing.use_zodiac_api_router",
    "Envelope routes must use `zodiac_core.routing.APIRouter`, not FastAPI's router.",
    "Import `APIRouter` from `zodiac_core.routing` so responses wrap as code/data/message.",
    "/api/routing/",
)
FASTAPI_API_ROUTER_IMPORT = Rule(
    "routing.fastapi_api_router_import",
    "Unused FastAPI `APIRouter` imports make it easy to build routes that bypass the Zodiac envelope.",
    "Remove the FastAPI import or replace it with `APIRouter` from `zodiac_core.routing`.",
    "/api/routing/",
    severity="warning",
)
USE_ZODIAC_EXCEPTION = Rule(
    "exceptions.use_zodiac_exception",
    "Business errors must raise `ZodiacException` subclasses so handlers emit the envelope.",
    "Replace `HTTPException` with `NotFoundException` or another Zodiac exception.",
    "/api/exceptions/",
)
NO_PARTIAL_GET_SESSION = Rule(
    "db.no_partial_get_session",
    "Named database dependencies must not wrap `get_session` with `functools.partial`.",
    'Bind once at module level with `session_dependency("name")`, then pass that callable to `Depends`.',
    "/api/db/",
)
NO_BARE_SESSION_DEPENDENCY = Rule(
    "db.no_bare_session_dependency",
    "`Depends(session_dependency)` treats the database name as a request parameter.",
    'Call `session_dependency("name")` at module level and pass that callable to `Depends`.',
    "/api/db/",
)
USE_ZODIAC_CLIENT = Rule(
    "http.use_zodiac_client",
    "Downstream HTTP calls must use `ZodiacClient` so request IDs propagate.",
    "Create the client with `init_http_client()` in the container and use `ZodiacClient`.",
    "/api/context/",
)
API_NO_INFRASTRUCTURE = Rule(
    "layers.api_no_infrastructure",
    "The API layer must not import infrastructure. Routers talk to services.",
    "Move data access into a repository and call it from an injected application service.",
    "/user-guide/architecture/",
)
SERVICE_NO_API_SCHEMAS = Rule(
    "layers.service_no_api_schemas",
    "Application services must not import API schemas. Pass validated fields from the router.",
    "Keep Pydantic schemas in `api/schemas/` and pass validated values into the service.",
    "/user-guide/architecture/",
)
SETUP_LOGURU_ONCE = Rule(
    "bootstrap.setup_loguru",
    "The process entry point must call `setup_loguru()` once.",
    "Call `setup_loguru(...)` once during process startup. Do not configure sinks from sub-applications.",
    "/api/logging/",
)
SUBAPP_NO_SETUP_LOGURU = Rule(
    "bootstrap.subapp_no_setup_loguru",
    "Sub-applications must not call `setup_loguru()`. The parent process owns logging.",
    "Remove `setup_loguru()` from the sub-app factory. Set identity with `register_middleware(app, service_name=...)`.",
    "/user-guide/sub-applications/",
)
REGISTER_EXCEPTION_HANDLERS = Rule(
    "bootstrap.register_exception_handlers",
    "Every FastAPI app that owns routes must call `register_exception_handlers(app)`.",
    "Call `register_exception_handlers(app)` in this factory after creating the app.",
    "/api/exceptions/",
)
REGISTER_PROCESS_MIDDLEWARE = Rule(
    "bootstrap.register_middleware",
    "A standard 3-tier app must register Zodiac middleware on the process app.",
    "Call `register_middleware(app, service_name=...)` in `create_app()`.",
    "/api/middleware/",
)
PARENT_NO_REGISTER_MIDDLEWARE = Rule(
    "bootstrap.parent_no_register_middleware",
    "Parent servers must not call `register_middleware()` for all routes; "
    "that duplicates trace IDs and access logs on mounts.",
    "Keep parent middleware scoped to parent-only paths. Register middleware on each mounted sub-application instead.",
    "/user-guide/sub-applications/",
)
SUBAPP_REGISTER_MIDDLEWARE = Rule(
    "bootstrap.subapp_register_middleware",
    "Each mounted sub-application must register its own middleware with a service name.",
    'Call `register_middleware(app, service_name="...")` in the sub-app factory.',
    "/user-guide/sub-applications/",
)


def parse_error(module_path: Path, line: int, column: int, found: str) -> Finding:
    return PARSE_ERROR.finding(path=module_path, line=line, column=column, found=found)


def check_api_router(module: ModuleView) -> list[Finding]:
    findings = [
        USE_ZODIAC_API_ROUTER.hit(module, call)
        for call in module.calls()
        if module.resolve(call.func) in FASTAPI_API_ROUTERS
    ]
    if findings:
        return findings
    return [
        FASTAPI_API_ROUTER_IMPORT.hit(
            module,
            line=symbol.line,
            column=symbol.column,
            found=symbol.found,
        )
        for symbol in module.imported_symbols
        if symbol.qualified in FASTAPI_API_ROUTERS
    ]


def check_http_exception(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        if module.resolve(target) in HTTP_EXCEPTIONS:
            findings.append(USE_ZODIAC_EXCEPTION.hit(module, node))
    return findings


def check_partial_get_session(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    for call in module.calls():
        if module.resolve(call.func) != "functools.partial" or not call.args:
            continue
        if module.resolve(call.args[0]) in GET_SESSION:
            findings.append(NO_PARTIAL_GET_SESSION.hit(module, call))
    return findings


def check_bare_session_dependency(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    for call in module.calls():
        if module.resolve(call.func) not in {"fastapi.Depends", "fastapi.params.Depends"}:
            continue
        if not call.args:
            continue
        if module.resolve(call.args[0]) in SESSION_DEPENDENCY:
            findings.append(NO_BARE_SESSION_DEPENDENCY.hit(module, call))
    return findings


def check_httpx_clients(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    for call in module.calls():
        qualified = module.resolve(call.func)
        if qualified in HTTPX_CLIENTS or qualified in HTTPX_SHORTCUTS:
            findings.append(USE_ZODIAC_CLIENT.hit(module, call))
    return findings


def check_layers(module: ModuleView) -> list[Finding]:
    if module.layer not in {"api", "application"}:
        return []
    findings: list[Finding] = []
    package = module.project.package_name
    for imported in module.imported_modules:
        if imported.module != package and not imported.module.startswith(f"{package}."):
            continue
        segments = imported.module.split(".")
        if module.layer == "api" and "infrastructure" in segments:
            findings.append(
                API_NO_INFRASTRUCTURE.hit(module, line=imported.line, column=imported.column, found=imported.found)
            )
        if module.layer == "application" and "api" in segments:
            findings.append(
                SERVICE_NO_API_SCHEMAS.hit(module, line=imported.line, column=imported.column, found=imported.found)
            )
    return findings


def check_setup_loguru(module: ModuleView) -> list[Finding]:
    if module.is_sub_app_factory and module.calls_name(None, SETUP_LOGURU):
        call = module.first_call(SETUP_LOGURU)
        return [SUBAPP_NO_SETUP_LOGURU.hit(module, call or module.tree)]
    return []


def missing_process_setup_loguru(project: Project) -> Finding:
    path = project.entry_relpath or Path("main.py")
    return SETUP_LOGURU_ONCE.finding(path=path, found=path.as_posix())


def check_app_factory_wiring(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    handlers = module.calls_name(None, REGISTER_HANDLERS)
    middleware = module.calls_name(None, REGISTER_MIDDLEWARE)
    for factory in module.app_factories():
        findings.extend(_factory_handler_findings(module, factory, handlers))
        findings.extend(_factory_middleware_findings(module, factory, middleware))
    return findings


def _factory_handler_findings(module: ModuleView, factory: FunctionNode, handlers_in_module: bool) -> list[Finding]:
    if module.calls_name(factory, REGISTER_HANDLERS) or handlers_in_module:
        return []
    node = module.first_call(FASTAPI_APP, factory) or factory
    return [REGISTER_EXCEPTION_HANDLERS.hit(module, node)]


def _factory_middleware_findings(
    module: ModuleView, factory: FunctionNode, middleware_in_module: bool
) -> list[Finding]:
    registered = module.calls_name(factory, REGISTER_MIDDLEWARE) or middleware_in_module
    layout = module.project.layout
    if module.is_app_entry and layout == LAYOUT_STANDARD and not registered:
        return [REGISTER_PROCESS_MIDDLEWARE.hit(module, factory)]
    if module.is_app_entry and layout == LAYOUT_SUB_APPLICATIONS and registered:
        node = module.first_call(REGISTER_MIDDLEWARE, factory) or factory
        return [PARENT_NO_REGISTER_MIDDLEWARE.hit(module, node)]
    if module.is_sub_app_factory and not registered:
        return [SUBAPP_REGISTER_MIDDLEWARE.hit(module, factory)]
    return []


RULES: tuple[RuleFn, ...] = (
    check_api_router,
    check_http_exception,
    check_partial_get_session,
    check_bare_session_dependency,
    check_httpx_clients,
    check_layers,
    check_setup_loguru,
    check_app_factory_wiring,
)


def check_module(module: ModuleView) -> list[Finding]:
    findings: list[Finding] = []
    for rule in RULES:
        findings.extend(rule(module))
    return findings
