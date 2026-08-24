#!/usr/bin/env python3
"""Resolve the ZodiacCore version and evidence sources for a working directory."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

DOCS_BASE_URL = "https://ttwshell.github.io/ZodiacCore-Py"
REQUIREMENT_PATTERN = re.compile(
    r"^\s*zodiac[-_]core(?:\[[^\]]+\])?\s*(?P<constraint>.*)$",
    re.IGNORECASE,
)
EXACT_VERSION_PATTERN = re.compile(r"^==\s*(?P<version>[A-Za-z0-9][A-Za-z0-9._+-]*)$")


def load_toml(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def project_name(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    name = data.get("project", {}).get("name")
    return str(name).lower().replace("_", "-") if name else None


def find_project_root(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    for directory in (current, *current.parents):
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file() or (directory / "uv.lock").is_file():
            return directory
        if any(directory.glob("requirements*.txt")):
            return directory
    return None


def is_source_tree(root: Path, pyproject: dict[str, Any] | None) -> bool:
    return project_name(pyproject) == "zodiac-core" and (root / "zodiac_core").is_dir() and (root / "docs").is_dir()


def git_value(root: Path, *args: str, allow_empty: bool = False) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and (value or allow_empty) else None


def source_context(root: Path, pyproject: dict[str, Any]) -> dict[str, Any]:
    version_value = pyproject.get("project", {}).get("version")
    version = str(version_value) if version_value else None
    status = git_value(root, "status", "--porcelain", allow_empty=True)
    return {
        "mode": "source-tree",
        "projectRoot": str(root),
        "version": version,
        "versionConstraint": None,
        "versionSource": "source-pyproject",
        "revision": git_value(root, "rev-parse", "--short", "HEAD"),
        "releaseTag": git_value(root, "describe", "--tags", "--exact-match", "HEAD"),
        "dirty": bool(status) if status is not None else None,
        "docsRoot": str(root / "docs"),
        "sourceRoot": str(root / "zodiac_core"),
        "publishedDocsUrl": versioned_docs_url(version),
    }


def requirement_details(requirement: str) -> tuple[str | None, str | None] | None:
    clean = requirement.split("#", 1)[0].strip()
    match = REQUIREMENT_PATTERN.match(clean)
    if not match:
        return None
    constraint = match.group("constraint").strip() or None
    if constraint and ";" in constraint:
        constraint = constraint.split(";", 1)[0].strip() or None
    exact_match = EXACT_VERSION_PATTERN.match(constraint or "")
    exact_version = exact_match.group("version") if exact_match else None
    return exact_version, constraint


def iter_dependency_strings(data: dict[str, Any] | None) -> list[str]:
    if not data:
        return []
    values: list[str] = []
    project = data.get("project", {})
    values.extend(item for item in project.get("dependencies", []) if isinstance(item, str))
    for dependencies in project.get("optional-dependencies", {}).values():
        values.extend(item for item in dependencies if isinstance(item, str))
    for dependencies in data.get("dependency-groups", {}).values():
        values.extend(item for item in dependencies if isinstance(item, str))
    return values


def version_from_uv_lock(root: Path) -> str | None:
    data = load_toml(root / "uv.lock")
    if not data:
        return None
    for package in data.get("package", []):
        name = str(package.get("name", "")).lower().replace("_", "-")
        version = package.get("version")
        if name == "zodiac-core" and version:
            return str(version)
    return None


def version_from_pyproject(
    data: dict[str, Any] | None,
) -> tuple[str | None, str | None] | None:
    for dependency in iter_dependency_strings(data):
        details = requirement_details(dependency)
        if details:
            return details
    return None


def version_from_requirements(root: Path) -> tuple[str | None, str | None, str] | None:
    for path in sorted(root.glob("requirements*.txt")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            details = requirement_details(line)
            if details:
                return details[0], details[1], path.name
    return None


def downstream_context(
    root: Path,
    pyproject: dict[str, Any] | None,
) -> dict[str, Any]:
    version = version_from_uv_lock(root)
    constraint: str | None = None
    source = "uv.lock" if version else "none"

    if not version:
        pyproject_details = version_from_pyproject(pyproject)
        if pyproject_details:
            version, constraint = pyproject_details
            source = "pyproject.toml"

    if not version and not constraint:
        requirements_details = version_from_requirements(root)
        if requirements_details:
            version, constraint, filename = requirements_details
            source = filename

    return {
        "mode": "downstream",
        "projectRoot": str(root),
        "version": version,
        "versionConstraint": constraint,
        "versionSource": source,
        "revision": None,
        "releaseTag": None,
        "dirty": None,
        "docsRoot": None,
        "sourceRoot": None,
        "publishedDocsUrl": versioned_docs_url(version) if version else None,
    }


def versioned_docs_url(version: str | None) -> str:
    suffix = version if version else "latest"
    return f"{DOCS_BASE_URL}/{suffix}/"


def resolve(path: Path) -> dict[str, Any]:
    target = path.expanduser().resolve()
    root = find_project_root(target)
    if root:
        pyproject = load_toml(root / "pyproject.toml")
        if is_source_tree(root, pyproject):
            return source_context(root, pyproject or {})
        return downstream_context(root, pyproject)
    return {
        "mode": "remote",
        "projectRoot": None,
        "version": None,
        "versionConstraint": None,
        "versionSource": "none",
        "revision": None,
        "releaseTag": None,
        "dirty": None,
        "docsRoot": None,
        "sourceRoot": None,
        "publishedDocsUrl": versioned_docs_url(None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve the ZodiacCore version and source context for a path.")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project path to inspect (default: current directory).",
    )
    args = parser.parse_args()
    print(json.dumps(resolve(args.path), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
