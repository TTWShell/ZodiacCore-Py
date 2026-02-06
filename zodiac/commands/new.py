"""zodiac new: generate a new project from a template."""

import os
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader

VALID_TEMPLATES = [
    "standard-3tier",
    # "ddd-4tier",
]


def get_template_path(template_id: str) -> Path:
    """Get the absolute path to the template directory."""
    return Path(__file__).parent.parent / "templates" / template_id


@click.command("new")
@click.argument("project_name", required=True)
@click.option(
    "--tpl",
    "template",
    required=True,
    type=click.Choice(VALID_TEMPLATES),
    help="Template id (standard-3tier or ddd-4tier).",
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
    help="Overwrite files in the target directory if it exists.",
)
def new_cmd(project_name: str, template: str, output_dir: str, force: bool) -> None:
    """Generate a new project from a template.

    PROJECT_NAME  Name of the project (required).
    """
    target_path = Path(output_dir) / project_name
    template_path = get_template_path(template)

    if target_path.exists() and not force:
        raise click.ClickException(f"Directory already exists: {target_path}. Use --force to overwrite.")

    click.echo(f"🚀 Generating project {project_name} using {template}...")

    env = Environment(loader=FileSystemLoader(str(template_path)))
    context = {
        "project_name": project_name,
        "template_id": template,
    }

    # Walk through template directory
    for root, _dirs, files in os.walk(template_path):
        rel_path = Path(root).relative_to(template_path)
        dest_dir = target_path / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            if not file.endswith(".jinja"):
                continue

            dest_file = dest_dir / file[:-6]  # Remove .jinja extension
            template_obj = env.get_template((rel_path / file).as_posix())
            rendered_content = template_obj.render(**context)
            dest_file.write_text(rendered_content, encoding="utf-8")

    click.echo(f"✅ Project created at: {target_path.absolute()}")
    click.echo("\nTo get started:")
    click.echo(f"  cd {target_path}")
    click.echo("  uv sync  # or pip install -e .")
