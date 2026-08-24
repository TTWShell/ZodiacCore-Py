"""Detect a ZodiacCore service from its dependency and layout."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

LAYOUT_STANDARD = "standard-3tier"
LAYOUT_SUB_APPLICATIONS = "sub-applications"
LAYOUT_SERVICE = "service"
_NOT_FOUND = (
    "Could not find a ZodiacCore service project. Run `zodiac check` from the "
    "service root (the directory with pyproject.toml), or pass that directory as PATH."
)
_NOT_ZODIAC = (
    "This project does not depend on zodiac-core. `zodiac check` only runs on "
    "services that declare zodiac-core in pyproject.toml or requirements.txt."
)


class ProjectError(Exception):
    """Raised when PATH is not a ZodiacCore service that `zodiac check` can verify."""


@dataclass(frozen=True)
class Project:
    """A ZodiacCore service project."""

    root: Path
    package_name: str
    layout: str
    entry_relpath: Path | None


def discover_project(path: Path) -> Project:
    """Resolve PATH, or a parent of PATH, to a ZodiacCore service project.

    If PATH itself contains `pyproject.toml`, it is the project to check.
    Otherwise walk upward until a ZodiacCore service project is found.
    """
    start = path.resolve()
    if not start.is_dir():
        raise ProjectError(f"Not a directory: {start}")
    if (start / "pyproject.toml").exists():
        return load_project(start)
    for candidate in start.parents:
        if (candidate / "pyproject.toml").exists():
            return load_project(candidate)
    raise ProjectError(_NOT_FOUND)


def load_project(path: Path) -> Project:
    """Resolve PATH to a ZodiacCore service project.

    A project is ours if it depends on `zodiac-core`. Layout is classified
    afterwards so 3-tier and sub-application rules can specialize, but a
    different package shape still gets the core wiring checks.
    """
    root = path.resolve()
    if not root.is_dir():
        raise ProjectError(f"Not a directory: {root}")

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise ProjectError(_NOT_FOUND)

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    if not _depends_on_zodiac_core(root, pyproject):
        raise ProjectError(_NOT_ZODIAC)

    package_name = _read_package_name(root, pyproject)
    layout, entry_relpath = _detect_layout(root, package_name)
    return Project(root=root, package_name=package_name, layout=layout, entry_relpath=entry_relpath)


def _depends_on_zodiac_core(root: Path, pyproject: dict) -> bool:
    project = pyproject.get("project", {})
    candidates = [
        project.get("dependencies", []),
        project.get("optional-dependencies", {}),
        pyproject.get("dependency-groups", {}),
        pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {}),
        pyproject.get("tool", {}).get("uv", {}).get("sources", {}),
    ]
    if any(_contains_zodiac_core(item) for item in candidates):
        return True
    for req_file in sorted(root.glob("requirements*.txt")):
        if "zodiac-core" in req_file.read_text(encoding="utf-8"):
            return True
    return False


def _contains_zodiac_core(value: object) -> bool:
    if isinstance(value, str):
        return "zodiac-core" in value
    if isinstance(value, dict):
        return any(key == "zodiac-core" or _contains_zodiac_core(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_zodiac_core(item) for item in value)
    return False


_SKIP_PACKAGE_NAMES = frozenset(
    {
        "tests",
        "unit_tests",
        "integration_tests",
        "test",
        "docs",
        "config",
        "outputs",
        "build",
        "dist",
        "site",
        "alembic",
        "migrations",
    }
)


def _iter_package_dirs(root: Path) -> Iterator[Path]:
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name.startswith(".") or child.name in _SKIP_PACKAGE_NAMES:
            continue
        yield child


def _read_package_name(root: Path, pyproject: dict) -> str:
    include = pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
    for pattern in include:
        if isinstance(pattern, str) and pattern.endswith("*"):
            package_name = pattern[:-1]
            if package_name and (root / package_name).is_dir():
                return package_name
    for child in _iter_package_dirs(root):
        if all((child / name).is_dir() for name in ("api", "application", "infrastructure")):
            return child.name
    for child in _iter_package_dirs(root):
        if (child / "main.py").is_file():
            return child.name
    return "app"


def _detect_layout(root: Path, package_name: str) -> tuple[str, Path | None]:
    package_root = root / package_name
    entry = _application_entry(root, package_name)
    entry_relpath = None if entry is None else entry.relative_to(root)
    if entry is not None and _main_defines_sub_applications(entry.read_text(encoding="utf-8")):
        return LAYOUT_SUB_APPLICATIONS, entry_relpath
    if package_root.is_dir() and all(
        (package_root / name).is_dir() for name in ("api", "application", "infrastructure")
    ):
        return LAYOUT_STANDARD, entry_relpath
    return LAYOUT_SERVICE, entry_relpath


def _application_entry(root: Path, package_name: str) -> Path | None:
    for candidate in (root / "main.py", root / package_name / "main.py"):
        if candidate.is_file():
            return candidate
    return None


def _main_defines_sub_applications(source: str) -> bool:
    """Detect mounted sub-apps from real calls, not comments or strings."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    has_mount = False
    has_lifespan_context = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mount":
            has_mount = True
        if isinstance(node, ast.Attribute) and node.attr == "lifespan_context":
            has_lifespan_context = True
        if has_mount and has_lifespan_context:
            return True
    return False
