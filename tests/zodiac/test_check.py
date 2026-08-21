"""Tests for `zodiac check`."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from zodiac.check import ProjectError, check_project, discover_project, render_report
from zodiac.check.module import ModuleView
from zodiac.check.project import load_project
from zodiac.main import cli


def generate_project(cli_runner, tmp_path: Path, *, template: str = "standard-3tier") -> Path:
    result = cli_runner.invoke(
        cli,
        ["new", "demo", "--tpl", template, "-o", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    return tmp_path / "demo"


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    assert old in content, f"marker not found in {path}: {old}"
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def rule_ids(result) -> set[str]:
    return {finding.rule_id for finding in result.findings}


def write_core_pyproject(root: Path, body: str = '[project]\nname = "demo"\ndependencies = ["zodiac-core"]\n') -> None:
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


class TestCheckCommand:
    def test_help(self, cli_runner):
        result = cli_runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        assert "wiring contract" in result.output
        assert "--format" in result.output

    def test_generated_standard_3tier_passes(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        result = cli_runner.invoke(cli, ["check", str(project)])
        assert result.exit_code == 0, result.output
        assert "passed" in result.output
        assert "standard-3tier" in result.output

    def test_generated_sub_applications_passes(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path, template="sub-applications")
        result = cli_runner.invoke(cli, ["check", str(project)])
        assert result.exit_code == 0, result.output
        assert "passed" in result.output
        assert "sub-applications" in result.output

    def test_rejects_non_project(self, cli_runner, tmp_path):
        result = cli_runner.invoke(cli, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "pyproject.toml" in result.output or "zodiac-core" in result.output

    def test_json_format_includes_change_direction(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "app" / "api" / "routers" / "item_router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter",
        )
        result = cli_runner.invoke(cli, ["check", str(project), "--format", "json"])
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert payload["layout"] == "standard-3tier"
        assert payload["rule_count"] == 1
        rule = payload["rules"][0]
        assert rule["rule_id"] == "routing.use_zodiac_api_router"
        assert rule["count"] == 1
        assert "APIRouter" in rule["hits"][0]["found"]
        assert "zodiac_core.routing" in rule["change"]
        assert rule["docs"].startswith("https://ttwshell.github.io/ZodiacCore-Py/")

    def test_discovers_project_from_subdirectory(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        result = cli_runner.invoke(cli, ["check", str(project / "app" / "api")])
        assert result.exit_code == 0, result.output
        assert "passed" in result.output

    def test_accepts_package_main_entry(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        (project / "app" / "main.py").write_text(
            (project / "main.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (project / "main.py").unlink()
        result = check_project(project)
        assert result.ok, render_report(result)
        assert result.layout == "standard-3tier"

    def test_setup_loguru_outside_entry_still_counts(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        main_py = project / "main.py"
        main_py.write_text(
            main_py.read_text(encoding="utf-8").replace("setup_loguru", "configure_logging"),
            encoding="utf-8",
        )
        container = project / "app" / "core" / "container.py"
        container.write_text(
            "from zodiac_core.logging import setup_loguru\n\nsetup_loguru(level='INFO')\n"
            + container.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = check_project(project)
        assert result.ok, render_report(result)
        assert "bootstrap.setup_loguru" not in rule_ids(result)

    def test_zodiac_core_dependency_is_enough(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\ndependencies = ["zodiac-core==0.9.1"]\n',
            encoding="utf-8",
        )
        (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
        result = check_project(tmp_path)
        assert result.layout == "service"
        assert result.ok, render_report(result)

    def test_detects_non_app_package_directory(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "iam"\ndependencies = ["zodiac-core"]\n',
            encoding="utf-8",
        )
        for name in ("api", "application", "infrastructure"):
            (tmp_path / "iam" / name).mkdir(parents=True)
        (tmp_path / "iam" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        result = check_project(tmp_path)
        assert result.package_name == "iam"
        assert result.layout == "standard-3tier"

    def test_rejects_project_without_zodiac_core(self, cli_runner, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "demo"\ndependencies = ["fastapi"]\n',
            encoding="utf-8",
        )
        (tmp_path / "app").mkdir()
        result = cli_runner.invoke(cli, ["check", str(tmp_path)])
        assert result.exit_code != 0
        assert "zodiac-core" in result.output


class TestCheckRules:
    def test_fastapi_api_router(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "app" / "api" / "routers" / "item_router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter",
        )
        result = check_project(project)
        assert "routing.use_zodiac_api_router" in rule_ids(result)
        finding = next(item for item in result.findings if item.rule_id == "routing.use_zodiac_api_router")
        assert "Import `APIRouter` from `zodiac_core.routing`" in finding.change

    def test_http_exception(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        service = project / "app" / "application" / "services" / "item_service.py"
        replace_once(
            service,
            "from zodiac_core.exceptions import NotFoundException",
            "from fastapi import HTTPException",
        )
        replace_once(
            service,
            "raise NotFoundException(message=f\"Item id '{item_id}' not found\")",
            'raise HTTPException(status_code=404, detail="missing")',
        )
        result = check_project(project)
        assert "exceptions.use_zodiac_exception" in rule_ids(result)

    def test_partial_get_session(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        router = project / "app" / "api" / "routers" / "item_router.py"
        content = router.read_text(encoding="utf-8")
        router.write_text(
            "from functools import partial\nfrom zodiac_core.db import get_session\n" + content,
            encoding="utf-8",
        )
        replace_once(
            router,
            "service: Annotated[ItemService, Depends(Provide[Container.item_service])],",
            'service: Annotated[ItemService, Depends(partial(get_session, "analytics"))],',
        )
        result = check_project(project)
        assert "db.no_partial_get_session" in rule_ids(result)

    def test_bare_session_dependency(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        router = project / "app" / "api" / "routers" / "item_router.py"
        content = router.read_text(encoding="utf-8")
        router.write_text(
            "from zodiac_core.db import session_dependency\n" + content,
            encoding="utf-8",
        )
        replace_once(
            router,
            "service: Annotated[ItemService, Depends(Provide[Container.item_service])],",
            "service: Annotated[ItemService, Depends(session_dependency)],",
        )
        result = check_project(project)
        assert "db.no_bare_session_dependency" in rule_ids(result)

    def test_bare_session_dependency_attribute_access(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        router = project / "app" / "api" / "routers" / "item_router.py"
        content = router.read_text(encoding="utf-8")
        router.write_text("import zodiac_core.db as db\n" + content, encoding="utf-8")
        replace_once(
            router,
            "service: Annotated[ItemService, Depends(Provide[Container.item_service])],",
            "service: Annotated[ItemService, Depends(db.session_dependency)],",
        )
        result = check_project(project)
        assert "db.no_bare_session_dependency" in rule_ids(result)

    def test_called_session_dependency_is_allowed(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        router = project / "app" / "api" / "routers" / "item_router.py"
        content = router.read_text(encoding="utf-8")
        router.write_text(
            "from zodiac_core.db import session_dependency\n\n"
            'get_analytics_session = session_dependency("analytics")\n' + content,
            encoding="utf-8",
        )
        result = check_project(project)
        assert result.ok, render_report(result)
        assert "db.no_bare_session_dependency" not in rule_ids(result)

    def test_httpx_client(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        client = project / "app" / "infrastructure" / "external" / "github_client.py"
        replace_once(client, "from zodiac_core.http import ZodiacClient, translate_upstream_errors", "import httpx")
        replace_once(client, "def __init__(self, client: ZodiacClient) -> None:", "def __init__(self) -> None:")
        replace_once(client, "self.client = client", "self.client = httpx.AsyncClient()")
        result = check_project(project)
        assert "http.use_zodiac_client" in rule_ids(result)

    def test_httpx_imported_get_is_flagged(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        client = project / "app" / "infrastructure" / "external" / "github_client.py"
        client.write_text(
            client.read_text(encoding="utf-8")
            + '\nfrom httpx import get\n\n\ndef _fetch() -> str:\n    return get("https://example.com")\n',
            encoding="utf-8",
        )
        result = check_project(project)
        assert "http.use_zodiac_client" in rule_ids(result)

    def test_api_must_not_import_infrastructure(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        router = project / "app" / "api" / "routers" / "item_router.py"
        replace_once(
            router,
            "from app.core.container import Container",
            "from app.core.container import Container\n"
            "from app.infrastructure.database.models.item_model import ItemModel",
        )
        result = check_project(project)
        assert "layers.api_no_infrastructure" in rule_ids(result)

    def test_service_must_not_import_api_schemas(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        service = project / "app" / "application" / "services" / "item_service.py"
        replace_once(
            service,
            "from app.infrastructure.database.models.item_model import ItemModel",
            "from app.api.schemas.item_schema import ItemSchema\n"
            "from app.infrastructure.database.models.item_model import ItemModel",
        )
        result = check_project(project)
        assert "layers.service_no_api_schemas" in rule_ids(result)

    def test_missing_exception_handlers(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(project / "main.py", "    register_exception_handlers(app)\n", "")
        result = check_project(project)
        assert "bootstrap.register_exception_handlers" in rule_ids(result)

    def test_missing_setup_loguru(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        main_py = project / "main.py"
        main_py.write_text(
            main_py.read_text(encoding="utf-8").replace("setup_loguru", "configure_logging"), encoding="utf-8"
        )
        result = check_project(project)
        assert "bootstrap.setup_loguru" in rule_ids(result)

    def test_standard_entry_must_register_middleware(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "main.py",
            "    register_middleware(\n        app,\n        service_name=logging_cfg.service_name,\n"
            '        exclude_paths=["/api/v1/health"],\n    )\n',
            "",
        )
        result = check_project(project)
        assert "bootstrap.register_middleware" in rule_ids(result)

    def test_subapp_must_not_call_setup_loguru(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path, template="sub-applications")
        app_py = project / "app" / "users" / "app.py"
        replace_once(
            app_py,
            "from fastapi import FastAPI",
            "from fastapi import FastAPI\nfrom zodiac_core.logging import setup_loguru",
        )
        replace_once(
            app_py,
            '    register_middleware(app, service_name="users")\n',
            '    setup_loguru(level="INFO")\n    register_middleware(app, service_name="users")\n',
        )
        result = check_project(project)
        assert "bootstrap.subapp_no_setup_loguru" in rule_ids(result)

    def test_subapp_must_register_middleware(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path, template="sub-applications")
        replace_once(
            project / "app" / "users" / "app.py",
            '    register_middleware(app, service_name="users")\n',
            "",
        )
        result = check_project(project)
        assert "bootstrap.subapp_register_middleware" in rule_ids(result)

    def test_parent_must_not_register_middleware(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path, template="sub-applications")
        replace_once(
            project / "main.py",
            "from zodiac_core.middleware import AccessLogMiddleware, ServiceNameMiddleware, TraceIDMiddleware",
            "from zodiac_core.middleware import (\n"
            "    AccessLogMiddleware,\n"
            "    ServiceNameMiddleware,\n"
            "    TraceIDMiddleware,\n"
            "    register_middleware,\n"
            ")",
        )
        replace_once(
            project / "main.py",
            "    register_exception_handlers(app)",
            "    register_middleware(app, service_name=logging_cfg.service_name)\n    register_exception_handlers(app)",
        )
        result = check_project(project)
        assert "bootstrap.parent_no_register_middleware" in rule_ids(result)

    def test_report_lists_found_contract_and_change(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "app" / "api" / "routers" / "item_router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter",
        )
        report = render_report(check_project(project))
        assert "contract:" in report
        assert "change:" in report
        assert "routing.use_zodiac_api_router" in report
        assert "router = APIRouter()" in report

    def test_same_rule_hits_are_grouped(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "app" / "api" / "routers" / "item_router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter",
        )
        replace_once(
            project / "app" / "api" / "router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter",
        )
        result = check_project(project)
        report = render_report(result)
        payload = json.loads(render_report(result, "json"))
        assert result.rule_count == 1
        assert payload["rules"][0]["count"] == 2
        assert report.count("contract:") == 1
        assert report.count("change:") == 1
        assert "app/api/routers/item_router.py" in report
        assert "app/api/router.py" in report

    def test_unused_fastapi_api_router_import_is_warning(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        replace_once(
            project / "app" / "api" / "routers" / "item_router.py",
            "from zodiac_core.routing import APIRouter",
            "from fastapi import APIRouter\nfrom zodiac_core.routing import APIRouter",
        )
        result = check_project(project)
        assert result.ok, render_report(result)
        assert "routing.fastapi_api_router_import" in rule_ids(result)
        assert "routing.use_zodiac_api_router" not in rule_ids(result)
        assert result.warning_count == 1

    def test_same_file_bootstrap_helper_counts(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        main_py = project / "main.py"
        replace_once(main_py, "    register_exception_handlers(app)\n", "    _configure(app)\n")
        main_py.write_text(
            main_py.read_text(encoding="utf-8") + "\n\ndef _configure(app):\n    register_exception_handlers(app)\n",
            encoding="utf-8",
        )
        result = check_project(project)
        assert result.ok, render_report(result)
        assert "bootstrap.register_exception_handlers" not in rule_ids(result)

    def test_skips_virtualenv_and_alembic_trees(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        venv = project / "custom_venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
        (venv / "nasty.py").write_text("from fastapi import APIRouter\nAPIRouter()\n", encoding="utf-8")
        alembic = project / "alembic"
        alembic.mkdir()
        (alembic / "env.py").write_text(
            "from fastapi import APIRouter, HTTPException\nrouter = APIRouter()\n",
            encoding="utf-8",
        )
        result = check_project(project)
        assert result.ok, render_report(result)

    def test_comments_do_not_look_like_sub_applications(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        main_py = project / "main.py"
        main_py.write_text(
            "# later: app.mount('/legacy') and router.lifespan_context\n" + main_py.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = check_project(project)
        assert result.layout == "standard-3tier"
        assert result.ok, render_report(result)
        assert "bootstrap.parent_no_register_middleware" not in rule_ids(result)

    def test_httpx_imported_get_does_not_flag_other_get_calls(self, cli_runner, tmp_path):
        project = generate_project(cli_runner, tmp_path)
        client = project / "app" / "infrastructure" / "external" / "github_client.py"
        client.write_text(
            client.read_text(encoding="utf-8") + "\nfrom httpx import get\n\n\ndef _read(data: dict) -> object:\n"
            '    return data.get("url")\n',
            encoding="utf-8",
        )
        result = check_project(project)
        assert "http.use_zodiac_client" not in rule_ids(result)


class TestCheckDiscovery:
    def test_requirements_txt_is_enough_when_pyproject_has_no_core(self, tmp_path):
        write_core_pyproject(
            tmp_path,
            "[project]\n"
            'name = "demo"\n'
            'dependencies = ["fastapi"]\n'
            "\n"
            "[tool.poetry.dependencies]\n"
            'python = "^3.12"\n'
            "retries = 3\n",
        )
        (tmp_path / "requirements.txt").write_text("zodiac-core==0.9.1\n", encoding="utf-8")
        (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
        result = check_project(tmp_path)
        assert result.layout == "service"
        assert result.ok, render_report(result)

    def test_package_name_comes_from_directory_with_main(self, tmp_path):
        write_core_pyproject(tmp_path)
        (tmp_path / "svc").mkdir()
        (tmp_path / "svc" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        result = check_project(tmp_path)
        assert result.package_name == "svc"
        assert result.layout == "service"
        assert result.ok, render_report(result)

    def test_layout_without_application_entry(self, tmp_path):
        write_core_pyproject(tmp_path)
        for name in ("api", "application", "infrastructure"):
            (tmp_path / "app" / name).mkdir(parents=True)
        result = check_project(tmp_path)
        assert result.package_name == "app"
        assert result.layout == "standard-3tier"
        assert result.ok, render_report(result)

    def test_syntax_error_in_main_is_not_sub_applications(self, tmp_path):
        write_core_pyproject(tmp_path)
        (tmp_path / "main.py").write_text("def broken(\n", encoding="utf-8")
        result = check_project(tmp_path)
        assert result.layout == "service"
        assert "parse.syntax_error" in rule_ids(result)
        finding = next(item for item in result.findings if item.rule_id == "parse.syntax_error")
        assert "def broken(" in finding.found
        assert "Fix the syntax error" in finding.change

    def test_rejects_file_path(self, tmp_path):
        target = tmp_path / "notes.txt"
        target.write_text("not a project\n", encoding="utf-8")
        with pytest.raises(ProjectError, match="Not a directory"):
            discover_project(target)
        with pytest.raises(ProjectError, match="Not a directory"):
            load_project(target)

    def test_load_project_requires_pyproject(self, tmp_path):
        with pytest.raises(ProjectError, match="Could not find a ZodiacCore service project"):
            load_project(tmp_path)


class TestCheckParseAndImports:
    def test_type_checking_imports_are_ignored(self, tmp_path):
        write_core_pyproject(tmp_path)
        (tmp_path / "main.py").write_text(
            "from typing import TYPE_CHECKING\n"
            "import typing\n"
            "\n"
            "if TYPE_CHECKING:\n"
            "    import httpx\n"
            "    from httpx import AsyncClient\n"
            "\n"
            "if typing.TYPE_CHECKING:\n"
            "    from fastapi import APIRouter\n",
            encoding="utf-8",
        )
        result = check_project(tmp_path)
        assert result.ok, render_report(result)
        assert "http.use_zodiac_client" not in rule_ids(result)
        assert "routing.fastapi_api_router_import" not in rule_ids(result)

    def test_star_and_unresolved_relative_imports(self, tmp_path):
        write_core_pyproject(tmp_path)
        pkg = tmp_path / "svc"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
        (pkg / "util.py").write_text("from . import helpers\nfrom .helpers import VALUE\n", encoding="utf-8")
        (tmp_path / "main.py").write_text(
            "from os import *\nfrom . import helpers\nfrom ...outside import ghost\nprint('ok')\n",
            encoding="utf-8",
        )
        result = check_project(tmp_path)
        assert result.ok, render_report(result)

    def test_empty_depends_is_not_bare_session_dependency(self, tmp_path):
        write_core_pyproject(tmp_path)
        (tmp_path / "main.py").write_text(
            "from fastapi import Depends\n\n\ndef endpoint(dep=Depends()):\n    return dep\n",
            encoding="utf-8",
        )
        result = check_project(tmp_path)
        assert "db.no_bare_session_dependency" not in rule_ids(result)
        assert result.ok, render_report(result)

    def test_module_view_helpers(self, tmp_path):
        write_core_pyproject(tmp_path)
        source_path = tmp_path / "main.py"
        source_path.write_text("import os\nprint(os.getcwd())\n", encoding="utf-8")
        project = discover_project(tmp_path)
        module = ModuleView.parse(project, source_path)
        assert module.resolve(None) is None
        assert module.first_call("missing.fn") is None
        assert module.source_line(ast.Constant(value=1, lineno=99, col_offset=0)) == ""
        call = ast.parse("gone()").body[0].value
        assert module.resolve(ast.Attribute(value=call, attr="name", ctx=ast.Load())) == "name"
