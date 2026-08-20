"""Parsed Python module view used by contract rules."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from zodiac.check.project import LAYOUT_SUB_APPLICATIONS, Project

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class ImportedModule:
    line: int
    column: int
    module: str
    found: str


@dataclass(frozen=True)
class ImportedSymbol:
    line: int
    column: int
    qualified: str
    found: str


@dataclass
class ModuleView:
    """One application file: source, aliases, and resolved imports."""

    project: Project
    rel_path: Path
    source: str
    tree: ast.AST
    lines: list[str] = field(init=False)
    aliases: dict[str, str] = field(default_factory=dict)
    imported_modules: list[ImportedModule] = field(default_factory=list)
    imported_symbols: list[ImportedSymbol] = field(default_factory=list)
    call_names: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.lines = self.source.splitlines()
        _ImportCollector(self).visit(self.tree)
        for call in ast.walk(self.tree):
            if isinstance(call, ast.Call):
                qualified = self.resolve(call.func)
                if qualified:
                    self.call_names.add(qualified)

    @classmethod
    def parse(
        cls,
        project: Project,
        file_path: Path,
        source: str | None = None,
    ) -> ModuleView:
        if source is None:
            source = file_path.read_text(encoding="utf-8")
        rel_path = file_path.relative_to(project.root)
        tree = ast.parse(source, filename=str(rel_path))
        return cls(project=project, rel_path=rel_path, source=source, tree=tree)

    @property
    def module_name(self) -> str:
        return ".".join(self.rel_path.with_suffix("").parts)

    @property
    def is_app_entry(self) -> bool:
        return self.project.entry_relpath is not None and self.rel_path == self.project.entry_relpath

    @property
    def is_sub_app_factory(self) -> bool:
        if self.project.layout != LAYOUT_SUB_APPLICATIONS or self.is_app_entry:
            return False
        parts = self.rel_path.parts
        return self.rel_path.name == "app.py" and len(parts) >= 2 and parts[0] == self.project.package_name

    @property
    def layer(self) -> str | None:
        parts = self.rel_path.parts
        if len(parts) < 2 or parts[0] != self.project.package_name:
            return None
        top = parts[1]
        if top in {"api", "application", "infrastructure", "core", "domains"}:
            return top
        return None

    def source_line(self, node: ast.AST) -> str:
        lineno = getattr(node, "lineno", 1)
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def resolve(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self.resolve(node.value)
            if base is None:
                return node.attr
            return f"{base}.{node.attr}"
        return None

    def calls(self, node: ast.AST | None = None) -> Iterator[ast.Call]:
        for child in ast.walk(node or self.tree):
            if isinstance(child, ast.Call):
                yield child

    def functions(self) -> Iterator[FunctionNode]:
        for child in ast.walk(self.tree):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield child

    def app_factories(self) -> Iterator[FunctionNode]:
        for function in self.functions():
            if _is_app_factory(function.name) and self.calls_name(function, "fastapi.FastAPI"):
                yield function

    def has_call(self, qualified: str) -> bool:
        return qualified in self.call_names

    def calls_name(self, node: ast.AST | None, qualified: str) -> bool:
        if node is None:
            return self.has_call(qualified)
        return any(self.resolve(call.func) == qualified for call in self.calls(node))

    def first_call(self, qualified: str, node: ast.AST | None = None) -> ast.Call | None:
        for call in self.calls(node):
            if self.resolve(call.func) == qualified:
                return call
        return None


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, module: ModuleView) -> None:
        self.module = module
        self._type_checking = 0

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking(node.test):
            self._type_checking += 1
            self.generic_visit(node)
            self._type_checking -= 1
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        if self._type_checking:
            return
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.module.aliases[bound] = alias.name if alias.asname else alias.name.split(".")[0]
            self.module.imported_modules.append(
                ImportedModule(
                    line=node.lineno,
                    column=node.col_offset + 1,
                    module=alias.name,
                    found=self.module.source_line(node),
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._type_checking:
            return
        package = _resolve_import_from(self.module.module_name, node)
        if package:
            self.module.imported_modules.append(
                ImportedModule(
                    line=node.lineno,
                    column=node.col_offset + 1,
                    module=package,
                    found=self.module.source_line(node),
                )
            )
        for alias in node.names:
            if alias.name == "*" or not package:
                continue
            qualified = f"{package}.{alias.name}"
            self.module.aliases[alias.asname or alias.name] = qualified
            self.module.imported_symbols.append(
                ImportedSymbol(
                    line=node.lineno,
                    column=node.col_offset + 1,
                    qualified=qualified,
                    found=self.module.source_line(node),
                )
            )


def _is_app_factory(name: str) -> bool:
    return name == "create_app" or (name.startswith("create_") and name.endswith("_app"))


def _is_type_checking(test: ast.AST) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _resolve_import_from(current_module: str, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    parts = current_module.split(".")
    if node.level > len(parts):
        return node.module
    parent = parts[: -node.level]
    if node.module:
        return ".".join([*parent, *node.module.split(".")])
    return ".".join(parent) if parent else node.module
