"""zodiac check: verify a ZodiacCore service against the wiring contract."""

from pathlib import Path

import click

from zodiac.check import ProjectError, check_project, render_report


@click.command("check")
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="text for humans; json for tools and later agent skills.",
)
def check_cmd(path: Path | None, output_format: str) -> None:
    """Check a ZodiacCore service against the wiring contract.

    PATH  Service root with pyproject.toml. Defaults to the current directory.
    The application entry may be main.py or <package>/main.py.

    Prints each violation with the contract it broke and the required change.
    Exits 1 when any error is found.
    """
    project_root = (path or Path.cwd()).resolve()
    try:
        result = check_project(project_root)
    except ProjectError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(render_report(result, output_format), nl=False)
    if not result.ok:
        raise SystemExit(1)
