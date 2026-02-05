"""Tests for the Zodiac CLI entry point."""

from zodiac.main import cli


class TestCLI:
    """Tests for the main CLI entry point."""

    def test_cli_version(self, cli_runner):
        """Test that CLI shows version information."""
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cli_help(self, cli_runner):
        """Test that CLI shows help information."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Zodiac CLI" in result.output
        assert "new" in result.output

    def test_cli_no_command(self, cli_runner):
        """Test that CLI shows help when no command is provided."""
        result = cli_runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Zodiac CLI" in result.output

    def test_cli_invalid_command(self, cli_runner):
        """Test that CLI shows error for invalid command."""
        result = cli_runner.invoke(cli, ["invalid"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output
