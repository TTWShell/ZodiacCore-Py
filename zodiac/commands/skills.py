"""zodiac skills: install packaged agent skills into a service project."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar

import click

GITIGNORE_HEADER = "# ZodiacCore packaged skills (linked from the installed package; do not commit)"
DEFAULT_AGENT = "codex"
AGENT_SKILL_DIRS: dict[str, Path] = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
    "cursor": Path(".cursor") / "skills",
    "copilot": Path(".github") / "skills",
    "gemini": Path(".gemini") / "skills",
}
AGENT_CHOICES = (*AGENT_SKILL_DIRS, "all")
_AGENT_OPTION_HELP = (
    "Agent skill directory. Repeat to target more than one. "
    "codex=.agents/skills, claude=.claude/skills, cursor=.cursor/skills, "
    "copilot=.github/skills, gemini=.gemini/skills, all=every agent above."
)

_F = TypeVar("_F", bound=Callable[..., object])


def _is_link(destination: Path) -> bool:
    return destination.is_symlink() or destination.is_junction()


def _destination_present(destination: Path) -> bool:
    return destination.exists(follow_symlinks=False) or _is_link(destination)


def find_project_root(start: Path) -> Path:
    """Resolve PATH, or a parent of PATH, to the directory that contains pyproject.toml."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise click.ClickException(
        "Could not find a project root with pyproject.toml. "
        "Run `zodiac skills install` or `zodiac skills uninstall` from the service, "
        "or pass that directory as PATH."
    )


def packaged_skills_root() -> Path:
    """Return the skills directory shipped in the installed zodiac package."""
    return Path(__file__).resolve().parent.parent / "skills"


def iter_packaged_skills() -> list[Path]:
    root = packaged_skills_root()
    if not root.is_dir():
        raise click.ClickException(f"Packaged skills were not found at {root}. Reinstall zodiac-core[zodiac].")
    return sorted(child for child in root.iterdir() if child.is_dir() and (child / "SKILL.md").is_file())


def resolve_agents(agents: tuple[str, ...]) -> tuple[str, ...]:
    requested = tuple(agent.lower() for agent in agents) or (DEFAULT_AGENT,)
    if "all" in requested:
        return tuple(AGENT_SKILL_DIRS)
    unknown = [agent for agent in requested if agent not in AGENT_SKILL_DIRS]
    if unknown:
        raise click.ClickException(f"Unknown agent: {', '.join(unknown)}. Choose from: {', '.join(AGENT_CHOICES)}.")
    return tuple(dict.fromkeys(requested))


def skill_destination(project_root: Path, agent: str) -> Path:
    return project_root / AGENT_SKILL_DIRS[agent]


def gitignore_pattern(agent: str) -> str:
    return f"{AGENT_SKILL_DIRS[agent].as_posix()}/zodiac-*"


def _resolve_targets(start: Path, agents: tuple[str, ...]) -> tuple[Path, tuple[str, ...], list[Path]]:
    project_root = find_project_root(start)
    selected_agents = resolve_agents(agents)
    skills = iter_packaged_skills()
    if not skills:
        raise click.ClickException(f"No SKILL.md packages found under {packaged_skills_root()}.")
    return project_root, selected_agents, skills


def _iter_skill_paths(
    project_root: Path, agents: tuple[str, ...], skills: list[Path]
) -> Iterator[tuple[str, Path, Path]]:
    for agent in agents:
        destination_root = skill_destination(project_root, agent)
        for source in skills:
            yield agent, source, destination_root / source.name


def _copied_skill_paths(destinations: list[tuple[str, Path, Path]]) -> list[Path]:
    return [
        destination
        for _agent, _source, destination in destinations
        if _destination_present(destination) and not _is_link(destination)
    ]


def _gitignore_stripped_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def _already_linked(destination: Path, source: Path) -> bool:
    if not _is_link(destination):
        return False
    try:
        return destination.resolve() == source.resolve()
    except OSError:
        return False


def _remove_destination(destination: Path) -> None:
    if _is_link(destination):
        destination.unlink()
        return
    if destination.is_dir():
        shutil.rmtree(destination)
        return
    if _destination_present(destination):
        destination.unlink()


def _unix_hint(exc: OSError, destination: Path, source: Path) -> str:
    return (
        f"Could not create a symlink at {destination} -> {source}: {exc}\n"
        "This OS uses a directory symlink. Check write permission on "
        f"{destination.parent} and that the filesystem allows symbolic links."
    )


def _windows_hint(junction_exc: OSError, symlink_exc: OSError | None, destination: Path, source: Path) -> str:
    detail = str(junction_exc) if symlink_exc is None else f"{junction_exc}; symlink fallback: {symlink_exc}"
    return (
        f"Could not create a directory junction at {destination} -> {source}: {detail}\n"
        "On Windows, `zodiac skills install` uses a directory junction (`mklink /J`), "
        "which does not need Administrator. Check that you can write "
        f"{destination.parent} and that the project is on a local NTFS drive.\n"
        "If junction creation is blocked, enable Developer Mode and retry "
        "(Windows can then create a directory symlink instead)."
    )


def link_skill_directory(source: Path, destination: Path) -> str:
    """Link destination to source. Returns 'symlink' or 'junction'."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        try:
            import _winapi

            _winapi.CreateJunction(os.fspath(source), os.fspath(destination))
            return "junction"
        except OSError as junction_exc:
            # A failed junction can leave a partial directory behind. Clear it so
            # the symlink fallback (or a later retry) is not mistaken for a copied
            # skill directory that would then require --force.
            if _destination_present(destination):
                _remove_destination(destination)
            try:
                os.symlink(source, destination, target_is_directory=True)
                return "symlink"
            except OSError as symlink_exc:
                raise click.ClickException(
                    _windows_hint(junction_exc, symlink_exc, destination, source)
                ) from symlink_exc
    try:
        os.symlink(source, destination, target_is_directory=True)
    except OSError as exc:
        raise click.ClickException(_unix_hint(exc, destination, source)) from exc
    return "symlink"


def ensure_gitignore(project_root: Path, agents: tuple[str, ...]) -> bool:
    """Append packaged-skill ignore patterns if missing. Returns True when the file changed."""
    path = project_root / ".gitignore"
    patterns = [gitignore_pattern(agent) for agent in agents]
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    present = set(_gitignore_stripped_lines(existing))
    missing = [pattern for pattern in patterns if pattern not in present]
    if not missing:
        return False
    lines = [] if not existing else [existing.rstrip("\n"), ""]
    if GITIGNORE_HEADER not in present:
        lines.append(GITIGNORE_HEADER)
    lines.extend(missing)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def prune_gitignore(project_root: Path, agents: tuple[str, ...]) -> bool:
    """Remove packaged-skill ignore patterns for the selected agents. Returns True when the file changed."""
    path = project_root / ".gitignore"
    if not path.exists():
        return False
    drop = {gitignore_pattern(agent) for agent in agents}
    original = path.read_text(encoding="utf-8")
    kept = [line for line in original.splitlines() if line.strip() not in drop]
    remaining = set(_gitignore_stripped_lines("\n".join(kept)))
    if not any(gitignore_pattern(agent) in remaining for agent in AGENT_SKILL_DIRS):
        kept = [line for line in kept if line.strip() != GITIGNORE_HEADER]
    text = "\n".join(kept).strip()
    updated = f"{text}\n" if text else ""
    if updated == original:
        return False
    if not updated:
        path.unlink()
        return True
    path.write_text(updated, encoding="utf-8")
    return True


def _rmdir_empty_parents(start: Path, stop_at: Path) -> None:
    current = start
    while current != stop_at:
        if not current.is_dir():
            return
        try:
            next(current.iterdir())
        except StopIteration:
            current.rmdir()
            current = current.parent
            continue
        return


def _echo_gitignore_update(project_root: Path, changed: bool) -> None:
    if changed:
        click.echo(f"updated {project_root / '.gitignore'}")


def install_packaged_skills(
    project_root: Path,
    *,
    agents: tuple[str, ...] = (DEFAULT_AGENT,),
    force: bool = False,
) -> None:
    """Link packaged skills into the project and gitignore the destinations."""
    project_root, selected_agents, skills = _resolve_targets(project_root, agents)
    destinations = list(_iter_skill_paths(project_root, selected_agents, skills))
    copied = _copied_skill_paths(destinations)
    if copied and not force:
        listed = "\n".join(str(path) for path in copied)
        raise click.ClickException(
            "The following paths already exist. Re-run with --force to replace "
            f"copied skill directories with links to the installed package:\n{listed}"
        )

    for agent, source, destination in destinations:
        if _already_linked(destination, source):
            click.echo(f"unchanged [{agent}] {destination} -> {source}")
            continue
        if _destination_present(destination):
            _remove_destination(destination)
        kind = link_skill_directory(source, destination)
        click.echo(f"linked ({kind}) [{agent}] {destination} -> {source}")

    _echo_gitignore_update(project_root, ensure_gitignore(project_root, selected_agents))


def uninstall_packaged_skills(
    project_root: Path,
    *,
    agents: tuple[str, ...] = (DEFAULT_AGENT,),
    force: bool = False,
) -> None:
    """Remove packaged skill links and their gitignore patterns."""
    project_root, selected_agents, skills = _resolve_targets(project_root, agents)
    destinations = list(_iter_skill_paths(project_root, selected_agents, skills))
    copied = _copied_skill_paths(destinations)
    if copied and not force:
        listed = "\n".join(str(path) for path in copied)
        raise click.ClickException(
            f"The following paths are not links. Re-run with --force to delete copied skill directories:\n{listed}"
        )

    for agent, _source, destination in destinations:
        if not _destination_present(destination):
            click.echo(f"absent [{agent}] {destination}")
            continue
        _remove_destination(destination)
        click.echo(f"removed [{agent}] {destination}")
    for agent in selected_agents:
        destination_root = skill_destination(project_root, agent)
        if destination_root.exists():
            _rmdir_empty_parents(destination_root, project_root)

    _echo_gitignore_update(project_root, prune_gitignore(project_root, selected_agents))


def _with_project_and_agent(fn: _F) -> _F:
    fn = click.option(
        "--agent",
        "agents",
        type=click.Choice(AGENT_CHOICES, case_sensitive=False),
        multiple=True,
        default=(DEFAULT_AGENT,),
        show_default=True,
        help=_AGENT_OPTION_HELP,
    )(fn)
    return click.argument(
        "path",
        required=False,
        type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    )(fn)


@click.group("skills")
def skills_cmd() -> None:
    """Install or remove packaged agent skills in a service project."""


@skills_cmd.command("install")
@_with_project_and_agent
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Replace a copied skill directory at the destination. Stale links are retargeted without this flag.",
)
def skills_install_cmd(path: Path | None, agents: tuple[str, ...], force: bool) -> None:
    """Link packaged ZodiacCore skills into a project agent skill directory.

    PATH  Service root with pyproject.toml. Defaults to the current directory;
    a subdirectory walks up to that root.

    Defaults to Codex (`.agents/skills`). Creates a directory symlink on Unix
    and a directory junction on Windows. Packaged `zodiac-*` skills stay
    gitignored. Re-run after `uv sync`; existing links are retargeted to the
    current package. Use --force only to replace a copied directory.
    """
    install_packaged_skills(path or Path.cwd(), agents=agents, force=force)


@skills_cmd.command("uninstall")
@_with_project_and_agent
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Delete a copied skill directory at the destination. Links are removed without this flag.",
)
def skills_uninstall_cmd(path: Path | None, agents: tuple[str, ...], force: bool) -> None:
    """Remove packaged ZodiacCore skill links from a project agent skill directory.

    PATH  Service root with pyproject.toml. Defaults to the current directory;
    a subdirectory walks up to that root.

    Defaults to Codex (`.agents/skills`). Removes directory symlinks or
    junctions for packaged `zodiac-*` skills and drops their gitignore
    patterns. Other skills in the same directory are left in place. Use
    --force to delete a copied skill directory.
    """
    uninstall_packaged_skills(path or Path.cwd(), agents=agents, force=force)
