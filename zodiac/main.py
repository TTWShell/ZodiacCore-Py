"""Zodiac CLI: entry point for the `zodiac` console script."""

import click

from zodiac.commands import new_cmd


@click.group()
@click.version_option(package_name="zodiac-core")
def cli() -> None:
    """Zodiac CLI: scaffold and manage Zodiac-based projects."""
    pass


cli.add_command(new_cmd)


def main() -> None:
    """Entry point for [project.scripts] zodiac = zodiac.main:main."""
    cli()


if __name__ == "__main__":
    main()
