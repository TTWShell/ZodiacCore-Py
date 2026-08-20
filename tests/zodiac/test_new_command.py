"""Tests for the `zodiac new` command."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click import ClickException

from zodiac.commands.add import (
    ensure_sub_applications_project,
    get_project_package_name,
    pluralize_identifier,
)
from zodiac.commands.new import get_template_path
from zodiac.main import cli


def isolated_project_environment() -> dict[str, str]:
    """Return an environment isolated from the outer test runner."""
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        env.pop(key, None)
        env.pop(key.lower(), None)
    for key in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(key, None)
    return env


def wire_generated_sub_app(main_path: Path, *, package_name: str, service_name: str) -> None:
    """Apply the CLI's printed wiring contract in a generated quality-test project."""
    content = main_path.read_text(encoding="utf-8")
    replacements = [
        (
            f"from {package_name}.core.config import CacheConfig, DbConfig, LoggingConfig",
            f"from {package_name}.{service_name}.app import create_{service_name}_app\n"
            f"from {package_name}.core.config import CacheConfig, DbConfig, LoggingConfig",
        ),
        (
            "orders_app = create_orders_app()",
            f"{service_name}_app = create_{service_name}_app()\norders_app = create_orders_app()",
        ),
        (
            "await stack.enter_async_context(orders_app.router.lifespan_context(orders_app))",
            f"await stack.enter_async_context({service_name}_app.router.lifespan_context({service_name}_app))\n"
            "        await stack.enter_async_context(orders_app.router.lifespan_context(orders_app))",
        ),
        (
            'app.mount("/users", users_app)',
            f'app.mount("/{service_name}", {service_name}_app)\n    app.mount("/users", users_app)',
        ),
    ]
    for old, new in replacements:
        assert old in content, f"Generated main.py wiring marker changed: {old}"
        content = content.replace(old, new, 1)

    lines = content.splitlines()
    package_import_indexes = [index for index, line in enumerate(lines) if line.startswith(f"from {package_name}.")]
    sorted_package_imports = sorted(lines[index] for index in package_import_indexes)
    for index, import_line in zip(package_import_indexes, sorted_package_imports, strict=True):
        lines[index] = import_line
    content = "\n".join(lines) + "\n"
    main_path.write_text(content, encoding="utf-8")


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
        assert "uv run zodiac check" in result.output
        assert '"zodiac-core[zodiac]"' in (target_path / "pyproject.toml").read_text()
        assert "uv run zodiac check" in (target_path / "README.md").read_text()

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
        assert "Use --force to generate into the existing directory" in result.output

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
        assert 'exclude_paths=["/api/v1/health"]' in content
        assert "ConfigManagement.provide_config(container.config.logging(), LoggingConfig)" in content
        assert "level=logging_cfg.level" in content
        assert "json_format=logging_cfg.json_format" in content
        assert "service_name=logging_cfg.service_name" in content
        assert 'level="INFO"' not in content

        # Check that project_name is rendered in pyproject.toml
        pyproject = target_path / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert f'name = "{project_name}"' in content
        assert '"pytest-env>=1.1.0"' in content
        assert '"APPLICATION_ENVIRONMENT=testing"' in content

        # Check that project_name is rendered in README.md
        readme = target_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert project_name in content
        assert "APPLICATION_ENVIRONMENT" in content
        assert "uv run uvicorn main:app --no-access-log" in content

        container_py = target_path / "app" / "core" / "container.py"
        assert container_py.exists()
        content = container_py.read_text()
        assert 'default_env="develop"' in content

        testing_config = (target_path / "config" / "app.testing.ini").read_text()
        assert "url = sqlite+aiosqlite:///:memory:" in testing_config
        assert "level = WARNING" in testing_config

        core_config = (target_path / "app" / "core" / "config.py").read_text()
        assert "class LoggingConfig" in core_config

    def test_new_command_custom_package_name(self, cli_runner):
        """Test that new command can generate a custom import package name."""
        project_name = "custom-package-project"
        package_name = "svc_a"
        target_path = self.test_output_dir / project_name

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
                "--package-name",
                package_name,
            ],
        )

        assert result.exit_code == 0
        assert (target_path / package_name).exists()
        assert not (target_path / "app").exists()

        main_py = (target_path / "main.py").read_text()
        assert f"from {package_name}.core.config import CacheConfig, DbConfig, LoggingConfig" in main_py
        assert f"from {package_name}.api.router import api_router" in main_py

        pyproject = (target_path / "pyproject.toml").read_text()
        assert f'include = ["{package_name}*"]' in pyproject

    def test_new_command_sub_applications_template(self, cli_runner):
        """Test that the sub-applications template generates a mounted services project."""
        project_name = "test-sub-applications"
        target_path = self.test_output_dir / project_name

        result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )

        assert result.exit_code == 0
        assert (target_path / "main.py").exists()
        assert (target_path / "AGENTS.md").exists()
        assert not (target_path / "CLAUDE.md").exists()
        assert (target_path / "app" / "orders" / "app.py").exists()
        assert (target_path / "app" / "users" / "app.py").exists()
        assert (target_path / "app" / "orders" / "core" / "container.py").exists()
        assert (target_path / "app" / "users" / "core" / "container.py").exists()
        assert (target_path / "app" / "orders" / "api" / "routers" / "order_router.py").exists()
        assert (target_path / "app" / "users" / "api" / "routers" / "user_router.py").exists()
        assert (target_path / "tests" / "conftest.py").exists()
        assert (target_path / "tests" / "test_health.py").exists()
        assert (target_path / "tests" / "orders" / "test_api.py").exists()
        assert (target_path / "tests" / "users" / "test_api.py").exists()

        main_py = (target_path / "main.py").read_text()
        assert 'app.mount("/users", users_app)' in main_py
        assert 'app.mount("/orders", orders_app)' in main_py
        assert "cache.setup(" in main_py
        assert "db.setup(" in main_py
        assert "register_exception_handlers(app)" in main_py
        assert "providers.Configuration(strict=True)" in main_py
        assert "container.config.from_ini(path, required=True)" in main_py
        assert "ConfigManagement.provide_config(container.config.logging(), LoggingConfig)" in main_py
        assert "service_name=logging_cfg.service_name" in main_py
        assert 'service_name="test-sub-applications"' not in main_py
        assert 'os.getenv("APPLICATION_ENVIRONMENT")' not in main_py
        assert main_py.index("db.setup(") < main_py.index("orders_app.router.lifespan_context")
        assert main_py.index("cache.setup(") < main_py.index("orders_app.router.lifespan_context")
        testing_config = (target_path / "config" / "app.testing.ini").read_text()
        assert "[logging]" in testing_config
        assert "level = WARNING" in testing_config
        generated_pyproject = (target_path / "pyproject.toml").read_text()
        assert '"zodiac-core[sql,cache]"' in generated_pyproject
        assert '"zodiac-core[zodiac]"' in generated_pyproject
        assert '"zodiac-core[zodiac,sql,cache]"' not in generated_pyproject
        core_config = (target_path / "app" / "core" / "config.py").read_text()
        assert "class LoggingConfig" in core_config

        users_app_py = (target_path / "app" / "users" / "app.py").read_text()
        orders_app_py = (target_path / "app" / "orders" / "app.py").read_text()
        assert 'register_middleware(app, service_name="users")' in users_app_py
        assert 'register_middleware(app, service_name="orders")' in orders_app_py
        assert "register_exception_handlers(app)" in users_app_py
        assert "register_exception_handlers(app)" in orders_app_py
        assert "Container" in users_app_py
        assert "Container" in orders_app_py
        assert '"app.users.api.router"' in users_app_py
        assert '"app.orders.api.router"' in orders_app_py

        user_service_py = (target_path / "app" / "users" / "application" / "services" / "user_service.py").read_text()
        order_service_py = (
            target_path / "app" / "orders" / "application" / "services" / "order_service.py"
        ).read_text()
        user_api_router_py = (target_path / "app" / "users" / "api" / "router.py").read_text()
        order_api_router_py = (target_path / "app" / "orders" / "api" / "router.py").read_text()
        user_model_py = (
            target_path / "app" / "users" / "infrastructure" / "database" / "models" / "user_model.py"
        ).read_text()
        order_model_py = (
            target_path / "app" / "orders" / "infrastructure" / "database" / "models" / "order_model.py"
        ).read_text()
        assert "repository: UserRepository | None" not in user_service_py
        assert "repository or UserRepository()" not in user_service_py
        assert "repository: OrderRepository | None" not in order_service_py
        assert "repository or OrderRepository()" not in order_service_py
        assert ".api.schemas" not in user_service_py
        assert ".api.schemas" not in order_service_py
        assert "name: str" in user_service_py
        assert "name: str" in order_service_py
        assert "UserService()" not in user_api_router_py
        assert "OrderService()" not in order_api_router_py
        user_resource_router_py = (target_path / "app" / "users" / "api" / "routers" / "user_router.py").read_text()
        order_resource_router_py = (target_path / "app" / "orders" / "api" / "routers" / "order_router.py").read_text()
        assert "service.create_user(payload.name)" in user_resource_router_py
        assert "service.create_order(payload.name)" in order_resource_router_py
        assert '__tablename__ = "user_users"' in user_model_py
        assert '__tablename__ = "order_orders"' in order_model_py

        user_schema_py = (target_path / "app" / "users" / "api" / "schemas" / "user_schema.py").read_text()
        order_schema_py = (target_path / "app" / "orders" / "api" / "schemas" / "order_schema.py").read_text()
        assert "from zodiac_core.schemas import CoreModel, IntIDSchema" in user_schema_py
        assert "from zodiac_core.schemas import CoreModel, IntIDSchema" in order_schema_py
        assert "class UserCreate(CoreModel)" in user_schema_py
        assert "class UserRead(IntIDSchema)" in user_schema_py
        assert "class OrderCreate(CoreModel)" in order_schema_py
        assert "class OrderRead(IntIDSchema)" in order_schema_py
        assert "ConfigDict(from_attributes=True)" not in user_schema_py
        assert "ConfigDict(from_attributes=True)" not in order_schema_py

        agents_md = (target_path / "AGENTS.md").read_text()
        assert "FastAPI multi-app server" in agents_md
        assert "ZodiacCore response envelope" in agents_md
        assert "Codex" in agents_md
        assert "Claude" not in agents_md
        assert "uv run zodiac check" in agents_md

        readme = (target_path / "README.md").read_text()
        assert "uv run uvicorn main:app --no-access-log" in readme

    def test_add_sub_app_generates_sub_application_without_patching_main(self, cli_runner, monkeypatch):
        """Test adding a sub-application skeleton to an existing mounted services project."""
        project_name = "test-add-sub-app"
        target_path = self.test_output_dir / project_name

        new_result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert new_result.exit_code == 0

        main_before = (target_path / "main.py").read_text()
        monkeypatch.chdir(target_path)
        add_result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert add_result.exit_code == 0
        assert "Sub-application created: billing" in add_result.output
        assert "from app.billing.app import create_billing_app" in add_result.output
        assert "billing_app = create_billing_app()" in add_result.output
        assert 'app.mount("/billing", billing_app)' in add_result.output
        assert "Wire the newly generated billing sub-application into main.py" in add_result.output

        assert (target_path / "main.py").read_text() == main_before
        assert (target_path / "app" / "billing" / "app.py").exists()
        assert (target_path / "app" / "billing" / "core" / "container.py").exists()
        assert (target_path / "app" / "billing" / "api" / "routers" / "item_router.py").exists()
        assert (target_path / "app" / "billing" / "api" / "schemas" / "item_schema.py").exists()
        assert (target_path / "tests" / "billing" / "test_api.py").exists()

        billing_app_py = (target_path / "app" / "billing" / "app.py").read_text()
        billing_router_py = (target_path / "app" / "billing" / "api" / "router.py").read_text()
        billing_model_py = (
            target_path / "app" / "billing" / "infrastructure" / "database" / "models" / "item_model.py"
        ).read_text()
        billing_test_py = (target_path / "tests" / "billing" / "test_api.py").read_text()
        assert "def create_billing_app() -> FastAPI:" in billing_app_py
        assert 'register_middleware(app, service_name="billing")' in billing_app_py
        assert '"app.billing.api.routers.item_router"' in billing_app_py
        assert 'prefix="/items"' in billing_router_py
        assert 'tags=["Items"]' in billing_router_py
        assert '__tablename__ = "billing_items"' in billing_model_py
        assert '"/billing"' in billing_test_py
        assert '"/api/v1/"' in billing_test_py
        assert '"items"' in billing_test_py

    @pytest.mark.parametrize("name", ["bad-name", "app", "core", "_"])
    def test_add_sub_app_rejects_invalid_service_name(self, cli_runner, name):
        result = cli_runner.invoke(cli, ["add", "sub-app", name])

        assert result.exit_code != 0
        assert "sub-application name" in result.output

    def test_add_sub_app_rejects_placeholder_resource_name(self, cli_runner):
        result = cli_runner.invoke(cli, ["add", "sub-app", "billing", "--resource", "_"])

        assert result.exit_code != 0
        assert "resource name must contain at least one non-underscore character" in result.output

    def test_add_sub_app_keeps_user_controlled_names_lint_clean(self, cli_runner, monkeypatch):
        """User-controlled resource and service names render without extra deny-lists."""
        target_path = self.test_output_dir / "test-add-sub-app-edge-names"
        result = cli_runner.invoke(
            cli,
            [
                "new",
                target_path.name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code == 0

        monkeypatch.chdir(target_path)
        cases = [
            ("catalog", ["--resource", "entry", "--resource-plural", "info"]),
            ("customer_relationship", ["--resource", "subscription_plan"]),
        ]
        for service_name, options in cases:
            result = cli_runner.invoke(cli, ["add", "sub-app", service_name, *options])
            assert result.exit_code == 0, result.output
            assert (target_path / "app" / service_name / "app.py").exists()
            assert (target_path / "tests" / service_name / "test_api.py").exists()

        catalog_router = (target_path / "app" / "catalog" / "api" / "router.py").read_text()
        catalog_tests = (target_path / "tests" / "catalog" / "test_api.py").read_text()
        assert 'prefix="/info"' in catalog_router
        assert '"/catalog"' in catalog_tests
        assert '"info"' in catalog_tests
        assert "service_info" not in catalog_router

        lint = subprocess.run(
            ["ruff", "check", "."],
            cwd=target_path,
            capture_output=True,
            text=True,
        )
        assert lint.returncode == 0, lint.stdout + lint.stderr

    def test_add_sub_app_requires_pyproject(self, cli_runner, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert result.exit_code != 0
        assert "project root with pyproject.toml" in result.output

    def test_get_project_package_name_falls_back_to_app(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'example'\n", encoding="utf-8")
        (tmp_path / "app").mkdir()

        assert get_project_package_name(tmp_path) == "app"

    def test_get_project_package_name_rejects_unknown_layout(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'example'\n", encoding="utf-8")

        with pytest.raises(ClickException, match="Could not detect the generated Python package"):
            get_project_package_name(tmp_path)

    def test_ensure_sub_applications_project_requires_main_and_package(self, tmp_path):
        with pytest.raises(ClickException, match="sub-applications project root"):
            ensure_sub_applications_project(tmp_path, "app")

    @pytest.mark.parametrize(
        ("singular", "plural"),
        [
            ("category", "categories"),
            ("person", "people"),
            ("audit_entry", "audit_entries"),
            ("type_", "types"),
            ("class_", "classes"),
        ],
    )
    def test_pluralize_identifier(self, singular, plural):
        """Resource plurals handle irregular nouns and snake_case identifiers."""
        assert pluralize_identifier(singular) == plural

    def test_add_sub_app_infers_irregular_resource_plural(self, cli_runner, monkeypatch):
        """Inferred plurals are used in routes, functions, and tables."""
        target_path = self.test_output_dir / "test-add-sub-app-plural"
        result = cli_runner.invoke(
            cli,
            [
                "new",
                target_path.name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code == 0

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(
            cli,
            [
                "add",
                "sub-app",
                "catalog",
                "--resource",
                "category",
            ],
        )

        assert result.exit_code == 0
        router = (target_path / "app" / "catalog" / "api" / "router.py").read_text()
        service = (target_path / "app" / "catalog" / "application" / "services" / "category_service.py").read_text()
        model = (
            target_path / "app" / "catalog" / "infrastructure" / "database" / "models" / "category_model.py"
        ).read_text()
        assert 'prefix="/categories"' in router
        assert 'tags=["Categories"]' in router
        assert "async def list_categories(" in service
        assert '__tablename__ = "catalog_categories"' in model

    def test_add_sub_app_infers_plural_for_keyword_safe_resource(self, cli_runner, monkeypatch):
        """Trailing underscores remain in singular identifiers but not inferred plurals."""
        target_path = self.test_output_dir / "test-add-sub-app-keyword-safe-resource"
        result = cli_runner.invoke(
            cli,
            [
                "new",
                target_path.name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code == 0

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(cli, ["add", "sub-app", "catalog", "--resource", "type_"])

        assert result.exit_code == 0
        router = (target_path / "app" / "catalog" / "api" / "router.py").read_text()
        resource_router = target_path / "app" / "catalog" / "api" / "routers" / "type__router.py"
        model = target_path / "app" / "catalog" / "infrastructure" / "database" / "models" / "type__model.py"
        assert 'prefix="/types"' in router
        assert resource_router.exists()
        assert '__tablename__ = "catalog_types"' in model.read_text()

    def test_add_sub_app_supports_resource_plural_override(self, cli_runner, monkeypatch):
        """Explicit plurals override the inferred English form."""
        target_path = self.test_output_dir / "test-add-sub-app-plural-override"
        result = cli_runner.invoke(
            cli,
            [
                "new",
                target_path.name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code == 0

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(
            cli,
            [
                "add",
                "sub-app",
                "directory",
                "--resource",
                "person",
                "--resource-plural",
                "persons",
            ],
        )

        assert result.exit_code == 0
        router = (target_path / "app" / "directory" / "api" / "router.py").read_text()
        service = (target_path / "app" / "directory" / "application" / "services" / "person_service.py").read_text()
        model = (
            target_path / "app" / "directory" / "infrastructure" / "database" / "models" / "person_model.py"
        ).read_text()
        assert 'prefix="/persons"' in router
        assert 'tags=["Persons"]' in router
        assert "async def list_persons(" in service
        assert '__tablename__ = "directory_persons"' in model

    def test_add_sub_app_preflights_all_conflicts_before_writing(self, cli_runner, monkeypatch):
        """A late conflict must not leave a partially generated application behind."""
        target_path = self.test_output_dir / "test-add-sub-app-conflict"
        result = cli_runner.invoke(
            cli,
            [
                "new",
                target_path.name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
            ],
        )
        assert result.exit_code == 0

        conflict = target_path / "tests" / "billing" / "test_api.py"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("existing\n", encoding="utf-8")
        monkeypatch.chdir(target_path)

        result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert result.exit_code != 0
        assert "File already exists" in result.output
        assert conflict.read_text(encoding="utf-8") == "existing\n"
        assert not (target_path / "app" / "billing").exists()

    def test_add_sub_app_rejects_non_sub_applications_project(self, cli_runner, monkeypatch):
        """Test that add sub-app only runs inside generated sub-applications projects."""
        project_name = "test-add-sub-app-invalid"
        target_path = self.test_output_dir / project_name

        new_result = cli_runner.invoke(
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
        assert new_result.exit_code == 0

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert result.exit_code != 0
        assert "sub-applications project root" in result.output

    def test_add_sub_app_detects_project_from_pyproject_and_main_only(self, cli_runner, monkeypatch):
        """Project detection must not depend on generated support files."""
        target_path = self.test_output_dir / "minimal-sub-applications"
        (target_path / "app").mkdir(parents=True)
        (target_path / "pyproject.toml").write_text(
            '[tool.setuptools.packages.find]\ninclude = ["app*"]\n',
            encoding="utf-8",
        )
        (target_path / "main.py").write_text(
            'def create_app():\n    app.mount("/users", users_app)\n    users_app.router.lifespan_context(users_app)\n',
            encoding="utf-8",
        )

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert result.exit_code == 0
        assert (target_path / "app" / "billing" / "app.py").exists()

    def test_add_sub_app_does_not_overwrite_outside_project(self, cli_runner, monkeypatch, tmp_path):
        """Setuptools package patterns must not redirect scaffold writes outside the project."""
        target_path = tmp_path / "project"
        target_path.mkdir()
        external_package = tmp_path / "external-package"
        external_billing = external_package / "billing"
        external_billing.mkdir(parents=True)
        sentinel = external_billing / "app.py"
        sentinel.write_text("# external sentinel\n", encoding="utf-8")
        (target_path / "pyproject.toml").write_text(
            f'[tool.setuptools.packages.find]\ninclude = ["{external_package.as_posix()}*"]\n',
            encoding="utf-8",
        )
        (target_path / "main.py").write_text(
            'def create_app():\n    app.mount("/users", users_app)\n    users_app.router.lifespan_context(users_app)\n',
            encoding="utf-8",
        )

        monkeypatch.chdir(target_path)
        result = cli_runner.invoke(cli, ["add", "sub-app", "billing", "--force"])

        assert result.exit_code != 0
        assert "Template destination escapes its output directory" in result.output
        assert sentinel.read_text(encoding="utf-8") == "# external sentinel\n"
        assert not (external_billing / "api").exists()

    def test_add_sub_app_respects_custom_package_name(self, cli_runner, monkeypatch):
        """Test that add sub-app detects and uses a custom generated package name."""
        project_name = "test-add-sub-app-custom-package"
        package_name = "svc_a"
        target_path = self.test_output_dir / project_name

        new_result = cli_runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "sub-applications",
                "-o",
                str(self.test_output_dir),
                "--package-name",
                package_name,
            ],
        )
        assert new_result.exit_code == 0

        monkeypatch.chdir(target_path)
        add_result = cli_runner.invoke(cli, ["add", "sub-app", "billing"])

        assert add_result.exit_code == 0
        assert "from svc_a.billing.app import create_billing_app" in add_result.output
        assert (target_path / package_name / "billing" / "app.py").exists()
        assert not (target_path / "app" / "billing").exists()

        billing_app_py = (target_path / package_name / "billing" / "app.py").read_text()
        assert "from .api.router import router" in billing_app_py
        assert "from .core.container import Container" in billing_app_py
        assert '"svc_a.billing.api.routers.item_router"' in billing_app_py

    @pytest.mark.parametrize("project_name", ["../escape", 'bad"name', ".", ".."])
    def test_new_command_rejects_unsafe_project_name(self, cli_runner, project_name):
        """Project names must not escape the output directory or break rendered config."""
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
        assert "must use only letters" in result.output

    @pytest.mark.parametrize(
        ("package_name", "error_message"),
        [
            ("bad-name", "must be a valid Python identifier"),
            ("main", "must not conflict with generated top-level modules"),
            ("config", "must not conflict with generated top-level modules"),
            ("tests", "must not conflict with generated top-level modules"),
        ],
    )
    def test_new_command_rejects_invalid_package_name(self, cli_runner, package_name, error_message):
        """Test that new command rejects package names that cannot be imported."""
        result = cli_runner.invoke(
            cli,
            [
                "new",
                "invalid-package-project",
                "--tpl",
                "standard-3tier",
                "-o",
                str(self.test_output_dir),
                "--package-name",
                package_name,
            ],
        )

        assert result.exit_code != 0
        assert error_message in result.output

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


@pytest.mark.serial
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
            '"zodiac-core[sql,cache]"',
            f'"zodiac-core[sql,cache] @ {repo_root.as_uri()}"',
        )
        pyproject_path.write_text(content)

        return target_path

    def test_generated_sub_applications_include_development_cli(self, generated_sub_applications_path):
        """Generated projects install the Zodiac CLI through their development extra."""
        assert (generated_sub_applications_path / "app" / "billing" / "app.py").exists()
        assert (generated_sub_applications_path / "tests" / "billing" / "test_api.py").exists()
        pyproject_content = (generated_sub_applications_path / "pyproject.toml").read_text()
        assert '"zodiac-core[zodiac]"' in pyproject_content
        main_content = (generated_sub_applications_path / "main.py").read_text()
        assert "from app.billing.app import create_billing_app" in main_content
        assert 'app.mount("/billing", billing_app)' in main_content

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
            ["uv", "sync", "--extra", "dev", "--reinstall-package", "zodiac-core"],
            cwd=generated_project_path,
            capture_output=True,
            text=True,
            env=isolated_project_environment(),
        )
        assert sync.returncode == 0, f"uv sync failed:\n{sync.stdout}\n{sync.stderr}"

        test = subprocess.run(
            ["uv", "run", "pytest", "-q"],
            cwd=generated_project_path,
            capture_output=True,
            text=True,
            env=isolated_project_environment(),
        )
        assert test.returncode == 0, f"generated project pytest failed:\n{test.stdout}\n{test.stderr}"
        assert not (generated_project_path / "data.db").exists()
        assert "GET /api/v1/items" not in test.stdout + test.stderr

    def test_generated_project_zodiac_check(self, generated_project_path):
        """Fresh standard-3tier projects must pass the ZodiacCore contract check."""
        from zodiac.check import check_project, render_report

        result = check_project(generated_project_path)
        assert result.ok, render_report(result)
        assert result.layout == "standard-3tier"

    @pytest.fixture(scope="class")
    def generated_sub_applications_path(self, tmp_path_factory):
        """Generate a sub-applications project once for all tests in this class."""
        from click.testing import CliRunner

        project_name = "test-sub-quality"
        test_output_dir = tmp_path_factory.mktemp("zodiac_sub_quality_test")
        target_path = test_output_dir / project_name

        if target_path.exists():
            shutil.rmtree(target_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "new",
                project_name,
                "--tpl",
                "sub-applications",
                "-o",
                str(test_output_dir),
            ],
        )
        assert result.exit_code == 0, f"Failed to generate project: {result.output}"
        assert target_path.exists(), f"Project was not created at {target_path}"

        repo_root = Path(__file__).resolve().parents[2]
        pyproject_path = target_path / "pyproject.toml"
        content = pyproject_path.read_text()
        content = content.replace(
            '"zodiac-core[sql,cache]"',
            f'"zodiac-core[sql,cache] @ {repo_root.as_uri()}"',
        )
        pyproject_path.write_text(content)

        sync = subprocess.run(
            ["uv", "sync", "--extra", "dev", "--reinstall-package", "zodiac-core"],
            cwd=target_path,
            capture_output=True,
            text=True,
            env=isolated_project_environment(),
        )
        assert sync.returncode == 0, f"uv sync failed:\n{sync.stdout}\n{sync.stderr}"

        sub_apps = [
            ("billing", ["--resource", "category", "--resource-plural", "categories"]),
            ("catalog", ["--resource", "entry", "--resource-plural", "info"]),
            ("customer_relationship", ["--resource", "subscription_plan"]),
        ]
        for service_name, options in sub_apps:
            add = subprocess.run(
                [
                    "uv",
                    "run",
                    "zodiac",
                    "add",
                    "sub-app",
                    service_name,
                    *options,
                ],
                cwd=target_path,
                capture_output=True,
                text=True,
                env=isolated_project_environment(),
            )
            assert add.returncode == 0, f"zodiac add failed:\n{add.stdout}\n{add.stderr}"
            wire_generated_sub_app(target_path / "main.py", package_name="app", service_name=service_name)

        return target_path

    def test_generated_sub_applications_ruff_lint(self, generated_sub_applications_path):
        """Test that generated sub-applications project passes ruff lint."""
        ruff_check_result = subprocess.run(
            ["ruff", "check", "."],
            cwd=generated_sub_applications_path,
            capture_output=True,
            text=True,
        )
        assert ruff_check_result.returncode == 0, (
            f"Ruff lint failed:\n{ruff_check_result.stdout}\n{ruff_check_result.stderr}"
        )

    def test_generated_sub_applications_pytest(self, generated_sub_applications_path):
        """Test that generated sub-applications project installs and passes pytest."""
        test = subprocess.run(
            ["uv", "run", "pytest", "-q"],
            cwd=generated_sub_applications_path,
            capture_output=True,
            text=True,
            env=isolated_project_environment(),
        )
        assert test.returncode == 0, f"generated sub-applications pytest failed:\n{test.stdout}\n{test.stderr}"
        output = test.stdout + test.stderr
        assert "GET /users/api/v1" not in output
        assert "GET /orders/api/v1" not in output
        assert "GET /billing/api/v1" not in output

    def test_generated_sub_applications_zodiac_check(self, generated_sub_applications_path):
        """Fresh sub-applications projects must pass the ZodiacCore contract check."""
        from zodiac.check import check_project, render_report

        result = check_project(generated_sub_applications_path)
        assert result.ok, render_report(result)
        assert result.layout == "sub-applications"
