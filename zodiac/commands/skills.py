"""zodiac skills: install packaged agent skills into a service project."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

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


def install_destination(project_root: Path, agent: str) -> Path:
    return project_root / AGENT_SKILL_DIRS[agent]


def gitignore_pattern(agent: str) -> str:
    return f"{AGENT_SKILL_DIRS[agent].as_posix()}/zodiac-*"


def _already_linked(destination: Path, source: Path) -> bool:
    if not destination.exists(follow_symlinks=False) and not destination.is_symlink() and not destination.is_junction():
        return False
    if not (destination.is_symlink() or destination.is_junction()):
        return False
    try:
        return destination.resolve() == source.resolve()
    except OSError:
        return False


def _remove_destination(destination: Path) -> None:
    if destination.is_symlink() or destination.is_junction():
        destination.unlink()
        return
    if destination.is_dir():
        shutil.rmtree(destination)
        return
    if destination.exists(follow_symlinks=False):
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
    missing = [pattern for pattern in patterns if pattern not in existing]
    if not missing:
        return False
    lines = [] if not existing else [existing.rstrip("\n"), ""]
    if GITIGNORE_HEADER not in existing:
        lines.append(GITIGNORE_HEADER)
    lines.extend(missing)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


@click.group("skills")
def skills_cmd() -> None:
    """Install packaged agent skills into a service project."""


@skills_cmd.command("install")
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--agent",
    "agents",
    type=click.Choice(AGENT_CHOICES, case_sensitive=False),
    multiple=True,
    default=(DEFAULT_AGENT,),
    show_default=True,
    help="Agent skill directory to install into. Repeat to target more than one. "
    "codex=.agents/skills, claude=.claude/skills, cursor=.cursor/skills, "
    "copilot=.github/skills, gemini=.gemini/skills, all=every agent above.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Replace an existing skill directory or link at the destination.",
)
def skills_install_cmd(path: Path | None, agents: tuple[str, ...], force: bool) -> None:
    """Link packaged ZodiacCore skills into a project agent skill directory.

    Defaults to Codex (`.agents/skills`). Creates a directory symlink on Unix
    and a directory junction on Windows. Packaged `zodiac-*` skills stay
    gitignored; re-run after `uv sync`.
    """
    project_root = (path or Path.cwd()).resolve()
    selected_agents = resolve_agents(agents)
    skills = iter_packaged_skills()
    if not skills:
        raise click.ClickException(f"No SKILL.md packages found under {packaged_skills_root()}.")

    for agent in selected_agents:
        destination_root = install_destination(project_root, agent)
        destination_root.mkdir(parents=True, exist_ok=True)
        for source in skills:
            destination = destination_root / source.name
            if _already_linked(destination, source):
                click.echo(f"unchanged [{agent}] {destination} -> {source}")
                continue
            if destination.exists(follow_symlinks=False) or destination.is_symlink() or destination.is_junction():
                if not force:
                    raise click.ClickException(
                        f"{destination} already exists. Re-run with --force to replace it with a link "
                        "to the installed package."
                    )
                _remove_destination(destination)
            kind = link_skill_directory(source, destination)
            click.echo(f"linked ({kind}) [{agent}] {destination} -> {source}")

    if ensure_gitignore(project_root, selected_agents):
        click.echo(f"updated {project_root / '.gitignore'}")
