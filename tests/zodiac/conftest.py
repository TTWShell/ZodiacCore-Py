"""Shared fixtures for Zodiac CLI tests."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide a CliRunner instance for CLI tests."""
    return CliRunner()
