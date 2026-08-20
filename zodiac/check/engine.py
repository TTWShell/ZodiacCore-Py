"""Walk a ZodiacCore service and run wiring contract rules."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from zodiac.check.models import CheckResult, Finding
from zodiac.check.module import ModuleView
from zodiac.check.project import Project, discover_project
from zodiac.check.rules import FASTAPI_APP, SETUP_LOGURU, check_module, missing_process_setup_loguru, parse_error

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        ".tox",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "build",
        "dist",
        "site",
        "node_modules",
        "tests",
        "unit_tests",
        "integration_tests",
        "test",
        "env",
        "alembic",
        "migrations",
        "htmlcov",
        ".nox",
        ".direnv",
        ".eggs",
        "__pypackages__",
    }
)

__all__ = ["check_project"]


def check_project(path: Path) -> CheckResult:
    """Check a ZodiacCore service and return machine-readable findings."""
    project = discover_project(path)
    files = list(_iter_python_files(project.root))
    findings: list[Finding] = []
    saw_setup_loguru = False
    saw_fastapi = False
    for file_path in files:
        file_findings, called_setup_loguru, called_fastapi = _check_file(project, file_path)
        findings.extend(file_findings)
        saw_setup_loguru = saw_setup_loguru or called_setup_loguru
        saw_fastapi = saw_fastapi or called_fastapi
    if saw_fastapi and not saw_setup_loguru:
        findings.append(missing_process_setup_loguru(project))
    findings.sort(key=lambda item: (item.path.as_posix(), item.line, item.column, item.rule_id))
    return CheckResult(
        project_root=project.root,
        layout=project.layout,
        package_name=project.package_name,
        file_count=len(files),
        findings=tuple(findings),
    )


def _iter_python_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if not _skip_directory(current / name))
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield current / filename


def _skip_directory(path: Path) -> bool:
    name = path.name
    if name in SKIP_DIR_NAMES or name.endswith(".egg-info"):
        return True
    return (path / "pyvenv.cfg").is_file()


def _check_file(project: Project, file_path: Path) -> tuple[list[Finding], bool, bool]:
    rel_path = file_path.relative_to(project.root)
    source = file_path.read_text(encoding="utf-8")
    try:
        module = ModuleView.parse(project, file_path, source=source)
    except SyntaxError as exc:
        found = (exc.text or (source.splitlines() or [""])[0]).strip()
        return [parse_error(rel_path, exc.lineno or 1, exc.offset or 1, found)], False, False
    return (
        check_module(module),
        module.has_call(SETUP_LOGURU),
        module.has_call(FASTAPI_APP),
    )
