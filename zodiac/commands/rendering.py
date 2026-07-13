"""Shared template planning and conflict-safe rendering utilities."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


@dataclass(frozen=True)
class RenderedFile:
    """A fully rendered file waiting to be written to disk."""

    destination: Path
    content: str


class TemplateConflictError(Exception):
    """Raised before writing when generated files already exist."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self.paths = tuple(paths)
        super().__init__(str(self.paths[0]))


class TemplatePathError(ValueError):
    """Raised when a rendered destination escapes its requested root."""


def build_render_plan(
    *,
    template_path: Path,
    destination_root: Path,
    context: dict[str, object],
    path_mapper: Callable[[Path], Path] | None = None,
) -> list[RenderedFile]:
    """Render every template in memory and return a deterministic write plan."""
    env = Environment(
        loader=FileSystemLoader(str(template_path)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    mapper = path_mapper or (lambda path: path)
    plan: list[RenderedFile] = []
    destinations: set[Path] = set()
    resolved_destination_root = destination_root.resolve()

    for source_path in sorted(template_path.rglob("*.jinja")):
        relative_source = source_path.relative_to(template_path)
        relative_destination = mapper(relative_source.with_suffix(""))
        destination = destination_root / relative_destination
        resolved_destination = destination.resolve()
        if not resolved_destination.is_relative_to(resolved_destination_root):
            raise TemplatePathError(f"Template destination escapes its output directory: {relative_destination}")
        if resolved_destination in destinations:
            raise ValueError(f"Multiple templates render to the same file: {destination}")
        destinations.add(resolved_destination)

        template = env.get_template(relative_source.as_posix())
        plan.append(RenderedFile(destination=destination, content=template.render(**context)))

    return plan


def write_render_plan(plan: Iterable[RenderedFile], *, force: bool = False) -> None:
    """Preflight all destinations, then write them with best-effort rollback."""
    rendered_files = list(plan)
    conflicts = [item.destination for item in rendered_files if item.destination.exists()]
    if conflicts and not force:
        raise TemplateConflictError(conflicts)

    original_contents = {
        item.destination: item.destination.read_bytes() for item in rendered_files if item.destination.exists()
    }
    created_files: list[Path] = []
    created_directories: set[Path] = set()

    try:
        for item in rendered_files:
            missing_parents = [parent for parent in item.destination.parents if not parent.exists()]
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            created_directories.update(missing_parents)
            if item.destination not in original_contents:
                created_files.append(item.destination)
            item.destination.write_text(item.content, encoding="utf-8")
    except Exception:
        for destination, content in original_contents.items():
            destination.write_bytes(content)
        for destination in reversed(created_files):
            destination.unlink(missing_ok=True)
        for directory in sorted(created_directories, key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
