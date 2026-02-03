"""zodiac new: generate a new project from a template."""

import click


@click.command("new")
@click.argument("project_name", required=True)
@click.option(
    "--tpl",
    "template",
    required=True,
    help="Template id (e.g. presentation-service-repository).",
)
@click.option(
    "-o",
    "--output",
    "output_dir",
    required=True,
    type=click.Path(path_type=str),
    help="Directory where the project will be generated.",
)
def new_cmd(project_name: str, template: str, output_dir: str) -> None:
    """Generate a new project from a template.

    PROJECT_NAME  Name of the project (required).
    """
    click.echo(f"Project: {project_name}")
    click.echo(f"Template: {template}")
    click.echo(f"Output: {output_dir}")
    click.echo("(scaffold not implemented yet)")
