"""zodiac new: generate a new project from a template."""

import keyword
import re
from pathlib import Path

import click

from zodiac.commands.rendering import build_render_plan, write_render_plan

VALID_TEMPLATES = [
    "standard-3tier",
    "sub-applications",
]
RESERVED_PACKAGE_NAMES = frozenset({"config", "main", "tests"})
PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def get_template_path(template_id: str) -> Path:
    """Get the absolute path to the template directory."""
    return Path(__file__).parent.parent / "templates" / template_id


def validate_package_name(_ctx: click.Context, _param: click.Parameter, value: str) -> str:
    """Validate that the package name can be used as a Python import package."""
    if not value.isidentifier() or keyword.iskeyword(value):
        raise click.BadParameter("must be a valid Python identifier, for example: app, svc_a, user_service")
    if value in RESERVED_PACKAGE_NAMES:
        raise click.BadParameter("must not conflict with generated top-level modules: config, main, tests")
    return value


def validate_project_name(_ctx: click.Context, _param: click.Parameter, value: str) -> str:
    """Reject project names that cannot be safely rendered into paths and config files."""
    if value in {".", ".."} or PROJECT_NAME_PATTERN.fullmatch(value) is None:
        raise click.BadParameter("must use only letters, numbers, dots, underscores, and hyphens")
    return value


def render_template_path(rel_path: Path, package_name: str) -> Path:
    """Map the template's default app package directory to the requested package name."""
    return Path(*(package_name if part == "app" else part for part in rel_path.parts))


@click.command("new")
@click.argument("project_name", required=True, callback=validate_project_name)
@click.option(
    "--tpl",
    "template",
    required=True,
    type=click.Choice(VALID_TEMPLATES),
    help="Template id (standard-3tier or sub-applications).",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    required=True,
    type=click.Path(path_type=str),
    help="Directory where the project will be generated.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Allow generating into an existing target directory without removing unrelated files.",
)
@click.option(
    "--package-name",
    default="app",
    show_default=True,
    callback=validate_package_name,
    help="Python package name generated inside the project.",
)
def new_cmd(project_name: str, template: str, output_dir: str, force: bool, package_name: str) -> None:
    """Generate a new project from a template.

    PROJECT_NAME  Name of the project (required).
    """
    target_path = Path(output_dir) / project_name
    template_path = get_template_path(template)

    if target_path.exists() and not force:
        raise click.ClickException(
            f"Directory already exists: {target_path}. Use --force to generate into the existing directory."
        )

    click.echo(f"🚀 Generating project {project_name} using {template}...")

    context = {
        "project_name": project_name,
        "package_name": package_name,
        "template_id": template,
    }

    plan = build_render_plan(
        template_path=template_path,
        destination_root=target_path,
        context=context,
        path_mapper=lambda path: render_template_path(path, package_name),
    )
    write_render_plan(plan, force=force)

    click.echo(f"✅ Project created at: {target_path.absolute()}")
    click.echo("\nTo get started:")
    click.echo(f"  cd {target_path}")
    click.echo("  uv sync  # or pip install -e .")
