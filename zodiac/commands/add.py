"""zodiac add: extend an existing Zodiac project."""

import keyword
import tomllib
from pathlib import Path

import click

from zodiac.commands.rendering import TemplateConflictError, build_render_plan, write_render_plan

RESERVED_SUB_APP_NAMES = frozenset({"api", "app", "config", "core", "main", "tests"})


def get_sub_app_template_path() -> Path:
    """Get the absolute path to the reusable sub-application template."""
    return Path(__file__).parent.parent / "templates" / "sub-app"


def validate_identifier(name: str, *, label: str) -> str:
    """Validate a CLI-provided Python identifier."""
    if not name.isidentifier() or keyword.iskeyword(name):
        raise click.ClickException(f"{label} must be a valid Python identifier, for example: billing")
    if name in RESERVED_SUB_APP_NAMES:
        raise click.ClickException(
            f"{label} must not conflict with reserved project names: api, app, config, core, main, tests"
        )
    return name


def to_class_name(name: str) -> str:
    """Convert a snake_case identifier to a PascalCase class name."""
    return "".join(part.capitalize() for part in name.split("_"))


def get_project_package_name(project_root: Path) -> str:
    """Read the generated import package name from pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise click.ClickException("This command must be run from a ZodiacCore project root with pyproject.toml.")

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    include = pyproject.get("tool", {}).get("setuptools", {}).get("packages", {}).get("find", {}).get("include", [])
    for pattern in include:
        if isinstance(pattern, str) and pattern.endswith("*"):
            package_name = pattern[:-1]
            if package_name and (project_root / package_name).is_dir():
                return package_name

    if (project_root / "app").is_dir():
        return "app"

    raise click.ClickException(
        "Could not detect the generated Python package. Expected tool.setuptools package include."
    )


def ensure_sub_applications_project(project_root: Path, package_name: str) -> None:
    """Fail unless the current directory looks like a generated sub-applications project."""
    main_py = project_root / "main.py"
    package_root = project_root / package_name
    if not main_py.exists() or not package_root.exists():
        raise click.ClickException("This command must be run from a ZodiacCore sub-applications project root.")

    main_content = main_py.read_text(encoding="utf-8")
    required_markers = ("app.mount(", "router.lifespan_context", "create_app")
    if not all(marker in main_content for marker in required_markers):
        raise click.ClickException(
            "This command must be run from a ZodiacCore sub-applications project root. "
            "Expected mounted sub-applications in main.py."
        )

    if not (package_root / "core" / "config.py").exists():
        raise click.ClickException(
            "This command must be run from a ZodiacCore sub-applications project root. "
            f"Expected {package_name}/core/config.py."
        )


def render_sub_app_path(rel_path: Path, *, service_name: str, resource_name: str, package_name: str) -> Path:
    """Render path placeholders used by the sub-application unit template."""
    rendered_parts: list[str] = []
    for part in rel_path.parts:
        if part == "app":
            rendered_parts.append(package_name)
        elif part == "sub_app":
            rendered_parts.append(service_name)
        elif part.startswith("resource_"):
            rendered_parts.append(part.replace("resource", resource_name, 1))
        else:
            rendered_parts.append(part)
    return Path(*rendered_parts)


def render_sub_app_template(
    *,
    project_root: Path,
    service_name: str,
    resource_name: str,
    resource_plural: str,
    package_name: str,
    force: bool,
) -> None:
    """Render a reusable sub-application template into an existing project."""
    template_path = get_sub_app_template_path()
    context = {
        "package_name": package_name,
        "service_name": service_name,
        "service_class": to_class_name(service_name),
        "resource_name": resource_name,
        "resource_plural": resource_plural,
        "resource_plural_class": to_class_name(resource_plural),
        "resource_class": to_class_name(resource_name),
        "table_name": f"{service_name}_{resource_plural}",
    }

    plan = build_render_plan(
        template_path=template_path,
        destination_root=project_root,
        context=context,
        path_mapper=lambda path: render_sub_app_path(
            path,
            service_name=service_name,
            resource_name=resource_name,
            package_name=package_name,
        ),
    )
    try:
        write_render_plan(plan, force=force)
    except TemplateConflictError as exc:
        raise click.ClickException(
            f"File already exists: {exc.paths[0]}. Use --force to overwrite generated files."
        ) from exc


def print_sub_app_next_steps(*, service_name: str, package_name: str) -> None:
    """Print the manual/AI wiring instructions after generating a sub-app."""
    app_var = f"{service_name}_app"
    create_func = f"create_{service_name}_app"
    click.echo(f"Sub-application created: {service_name}")
    click.echo("\nNext steps:")
    click.echo("  1. Import and instantiate the new app in main.py:")
    click.echo(f"     from {package_name}.{service_name}.app import {create_func}")
    click.echo(f"     {app_var} = {create_func}()")
    click.echo("\n  2. Enter its lifespan after shared db/cache setup:")
    click.echo(f"     await stack.enter_async_context({app_var}.router.lifespan_context({app_var}))")
    click.echo("\n  3. Mount it in create_app():")
    click.echo(f'     app.mount("/{service_name}", {app_var})')
    click.echo("\n  4. Ask Codex to finish wiring if you want AI assistance:")
    click.echo(
        f'     "Wire the newly generated {service_name} sub-application into main.py following the existing '
        'users/orders pattern, then update tests."'
    )
    click.echo("\nRun tests after main.py is wired:")
    click.echo("  uv run pytest -q")


@click.group("add")
def add_cmd() -> None:
    """Add components to an existing Zodiac project."""


@add_cmd.command("sub-app")
@click.argument("name", required=True)
@click.option(
    "--resource",
    default="item",
    show_default=True,
    help="Example resource name generated inside the sub-application.",
)
@click.option(
    "--resource-plural",
    default=None,
    help="Plural resource name used in routes and generated function names.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite generated files if they already exist.",
)
def add_sub_app_new_cmd(name: str, resource: str, resource_plural: str | None, force: bool) -> None:
    """Generate a new mounted sub-application skeleton.

    NAME  Sub-application service name, for example billing.
    """
    service_name = validate_identifier(name, label="sub-application name")
    resource_name = validate_identifier(resource, label="resource name")
    plural_name = validate_identifier(resource_plural or f"{resource_name}s", label="resource plural")
    project_root = Path.cwd()
    package_name = get_project_package_name(project_root)

    ensure_sub_applications_project(project_root, package_name)
    render_sub_app_template(
        project_root=project_root,
        service_name=service_name,
        resource_name=resource_name,
        resource_plural=plural_name,
        package_name=package_name,
        force=force,
    )
    print_sub_app_next_steps(service_name=service_name, package_name=package_name)
