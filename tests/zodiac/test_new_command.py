"""Tests for the `zodiac new` command."""

import shutil
import subprocess
from pathlib import Path

import pytest

from zodiac.commands.new import get_template_path
from zodiac.main import cli


class TestNewCommand:
    """Tests for the `zodiac new` command."""

    @pytest.fixture(autouse=True)
    def setup_test_dir(self, tmp_path):
        """Set up test output directory for each test."""
        self.test_output_dir = tmp_path / "zodiac_test_output"
        self.test_output_dir.mkdir(exist_ok=True)

    def test_new_command_help(self, cli_runner):
        """Test that new command shows help information."""
        result = cli_runner.invoke(cli, ["new", "--help"])
        assert result.exit_code == 0
        assert "Generate a new project from a template" in result.output
        assert "--tpl" in result.output or "--template" in result.output
        assert "--output" in result.output or "-o" in result.output
        assert "--force" in result.output or "-f" in result.output

    def test_new_command_missing_arguments(self, cli_runner):
        """Test that new command fails with missing required arguments."""
        result = cli_runner.invoke(cli, ["new"])
        assert result.exit_code != 0

        result = cli_runner.invoke(cli, ["new", "test-project"])
        assert result.exit_code != 0

        result = cli_runner.invoke(cli, ["new", "test-project", "--tpl", "standard-3tier"])
        assert result.exit_code != 0

    def test_new_command_invalid_template(self, cli_runner):
        """Test that new command fails with invalid template."""
        result = cli_runner.invoke(
            cli,
            [
                "new",
                "test-project",
                "--tpl",
                "invalid-template",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code != 0
        assert "Error: Invalid value for '--tpl'" in result.output

    def test_new_command_success(self, cli_runner):
        """Test successful project generation."""
        project_name = "test-project-success"
        target_path = self.test_output_dir / project_name

        # Clean up if exists
        if target_path.exists():
            shutil.rmtree(target_path)

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
            ],
        )

        assert result.exit_code == 0
        assert "Generating project" in result.output or "🚀" in result.output
        assert "Project created at" in result.output or "✅" in result.output
        assert target_path.exists()
        assert (target_path / "main.py").exists()
        assert (target_path / "pyproject.toml").exists()
        assert (target_path / "README.md").exists()
        assert (target_path / "app").exists()
        assert (target_path / "config").exists()

    def test_new_command_directory_exists_without_force(self, cli_runner):
        """Test that new command fails when directory exists without --force."""
        project_name = "test-project-exists"
        target_path = self.test_output_dir / project_name

        # Create directory first
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / "existing_file.txt").write_text("test")

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
            ],
        )

        assert result.exit_code != 0
        assert "already exists" in result.output
        assert "Use --force to overwrite" in result.output

    def test_new_command_directory_exists_with_force(self, cli_runner):
        """Test that new command overwrites directory with --force."""
        project_name = "test-project-force"
        target_path = self.test_output_dir / project_name

        # Create directory with existing file
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / "old_file.txt").write_text("old content")

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert target_path.exists()
        assert (target_path / "old_file.txt").exists()
        assert (target_path / "main.py").exists()

    def test_new_command_template_rendering(self, cli_runner):
        """Test that template variables are correctly rendered."""
        project_name = "my-awesome-project"
        target_path = self.test_output_dir / project_name

        if target_path.exists():
            shutil.rmtree(target_path)

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
            ],
        )

        assert result.exit_code == 0

        # Check that project_name is rendered in main.py
        main_py = target_path / "main.py"
        assert main_py.exists()
        content = main_py.read_text()
        assert project_name in content

        # Check that project_name is rendered in pyproject.toml
        pyproject = target_path / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert f'name = "{project_name}"' in content

        # Check that project_name is rendered in README.md
        readme = target_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert project_name in content

    def test_new_command_file_and_directory_count(self, cli_runner):
        """Test that generated project has same file and directory count as template."""
        project_name = "test-count"
        target_path = self.test_output_dir / project_name

        if target_path.exists():
            shutil.rmtree(target_path)

        template_path = get_template_path("standard-3tier")

        # Count template files (.jinja) and directories
        template_jinja_files = list(template_path.rglob("*.jinja"))
        template_dirs = [d for d in template_path.rglob("*") if d.is_dir() and d != template_path]

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
            ],
        )

        assert result.exit_code == 0

        # Count generated files (non-jinja) and directories
        generated_files = [f for f in target_path.rglob("*") if f.is_file() and not f.name.endswith(".jinja")]
        generated_dirs = [d for d in target_path.rglob("*") if d.is_dir() and d != target_path]

        assert len(generated_files) == len(template_jinja_files), (
            f"File count mismatch: generated={len(generated_files)}, template={len(template_jinja_files)}"
        )
        assert len(generated_dirs) == len(template_dirs), (
            f"Directory count mismatch: generated={len(generated_dirs)}, template={len(template_dirs)}"
        )


class TestGeneratedProjectQuality:
    """Tests for verifying quality of generated projects (ruff lint, pytest)."""

    @pytest.fixture(scope="class")
    def generated_project_path(self, tmp_path_factory):
        """Generate a project once for all tests in this class."""
        from click.testing import CliRunner

        project_name = "test-quality-project"
        test_output_dir = tmp_path_factory.mktemp("zodiac_quality_test")
        target_path = test_output_dir / project_name

        if target_path.exists():
            shutil.rmtree(target_path)

        # Generate project
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(test_output_dir),
            ],
        )
        assert result.exit_code == 0, f"Failed to generate project: {result.output}"
        assert target_path.exists(), f"Project was not created at {target_path}"

        # Make generated project resolvable in this repo context:
        # point zodiac-core dependency to the local workspace path, instead of PyPI.
        repo_root = Path(__file__).resolve().parents[2]
        pyproject_path = target_path / "pyproject.toml"
        content = pyproject_path.read_text()
        content = content.replace(
            '"zodiac-core[sql]"',
            f'"zodiac-core[sql] @ {repo_root.as_uri()}"',
        )
        pyproject_path.write_text(content)

        return target_path

    def test_generated_project_ruff_lint(self, generated_project_path):
        """Test that generated project passes ruff lint."""
        ruff_check_result = subprocess.run(
            ["ruff", "check", "."],
            cwd=generated_project_path,
            capture_output=True,
            text=True,
        )
        assert ruff_check_result.returncode == 0, (
            f"Ruff lint failed after auto-fix:\n{ruff_check_result.stdout}\n{ruff_check_result.stderr}"
        )

    def test_generated_project_pytest(self, generated_project_path):
        """Test that generated project installs and passes pytest."""
        # Install the generated project's deps (including dev test deps) into its own .venv.
        sync = subprocess.run(
            ["uv", "sync", "--extra", "dev"],
            cwd=generated_project_path,
            capture_output=True,
            text=True,
        )
        assert sync.returncode == 0, f"uv sync failed:\n{sync.stdout}\n{sync.stderr}"

        test = subprocess.run(
            ["uv", "run", "pytest", "-q"],
            cwd=generated_project_path,
            capture_output=True,
            text=True,
        )
        assert test.returncode == 0, f"generated project pytest failed:\n{test.stdout}\n{test.stderr}"
