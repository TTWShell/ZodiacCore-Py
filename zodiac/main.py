"""Zodiac CLI: entry point for the `zodiac` console script."""

import click

from zodiac.commands import new_cmd


@click.group(invoke_without_command=True)
@click.version_option(package_name="zodiac-core")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Zodiac CLI: scaffold and manage Zodiac-based projects."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(new_cmd)


def main() -> None:
    """Entry point for [project.scripts] zodiac = zodiac.main:main."""
    cli()


if __name__ == "__main__":
    main()
