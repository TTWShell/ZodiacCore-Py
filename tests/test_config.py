import os
from types import SimpleNamespace

import pytest
from dependency_injector import containers, errors, providers
from loguru import logger
from pydantic import BaseModel, ValidationError

from zodiac_core import ConfigManagement, Environment, StrictConfig
from zodiac_core.utils import strtobool


def test_get_config_files_base_only(tmp_path):
    (tmp_path / "app.ini").touch()
    (tmp_path / "settings.ini").touch()

    # Use 'develop' as target_env
    files = ConfigManagement.get_config_files([tmp_path], env_var="TEST_ENV", default_env="develop")
    filenames = [os.path.basename(f) for f in files]
    assert sorted(filenames) == ["app.ini", "settings.ini"]


def test_get_config_files_with_env_override(tmp_path):
    (tmp_path / "app.ini").touch()
    (tmp_path / "app.develop.ini").touch()
    (tmp_path / "app.production.ini").touch()  # Known env, should be skipped silently

    # target_env is 'develop'
    files = ConfigManagement.get_config_files([tmp_path], env_var="TEST_ENV_2", default_env="develop")

    filenames = [os.path.basename(f) for f in files]
    assert "app.ini" in filenames
    assert "app.develop.ini" in filenames
    assert "app.production.ini" not in filenames
    assert filenames.index("app.ini") < filenames.index("app.develop.ini")


def test_get_config_files_logging_strict_env(tmp_path):
    # Setup
    (tmp_path / "app.production.ini").touch()
    (tmp_path / "app.dev.ini").touch()
    (tmp_path / "app.test.ini").touch()
    (tmp_path / "app.weirdo.ini").touch()

    logs = []
    handler_id = logger.add(logs.append, format="{message}")

    try:
        # target_env is 'production'
        ConfigManagement.get_config_files([tmp_path], env_var="TEST_ENV_LOG", default_env="production")
    finally:
        logger.remove(handler_id)

    log_messages = [str(log) for log in logs]

    # Check strict matches are NOT logged
    assert not any("app.production.ini" in m for m in log_messages)

    # Check non-strict or unknown aliases ARE logged
    assert any("app.dev.ini" in m for m in log_messages)
    assert any("app.test.ini" in m for m in log_messages)
    assert any("app.weirdo.ini" in m for m in log_messages)


def test_environment_enum_values():
    assert Environment.DEVELOP == "develop"
    assert Environment.TESTING == "testing"
    assert Environment.STAGING == "staging"
    assert Environment.PRODUCTION == "production"
    assert len(Environment) == 4


def test_provide_config_recursive_list():
    config_dict = {
        "services": [
            {"name": "auth", "port": 8080},
            {"name": "gateway", "port": 80},
        ],
        "meta": {"tags": ["api", "v1"]},
    }
    config_obj = ConfigManagement.provide_config(config_dict)

    assert isinstance(config_obj.services[0], SimpleNamespace)
    assert config_obj.services[0].name == "auth"
    assert config_obj.services[1].port == 80
    assert config_obj.meta.tags == ["api", "v1"]


def test_get_config_files_complex_filename(tmp_path):
    # Test file with multiple dots
    (tmp_path / "my.app.service.develop.ini").touch()

    files = ConfigManagement.get_config_files([tmp_path], env_var="TEST_ENV_COMPLEX", default_env="develop")
    filenames = [os.path.basename(f) for f in files]
    assert "my.app.service.develop.ini" in filenames


def test_get_config_files_invalid_paths(tmp_path):
    # Test with non-existent directory
    invalid_path = tmp_path / "ghost_dir"

    # Should not raise exception, just return empty list or skip
    files = ConfigManagement.get_config_files([invalid_path], default_env="develop")
    assert len(files) == 0


class DbConfig(BaseModel):
    host: str
    port: int = 5432


class AppConfig(BaseModel):
    db: DbConfig
    debug: bool = False


def test_provide_config_with_pydantic_model():
    """Test provide_config with Pydantic model for type-safe config."""
    config_dict = {"db": {"host": "localhost", "port": 3306}, "debug": True}

    config = ConfigManagement.provide_config(config_dict, AppConfig)

    assert isinstance(config, AppConfig)
    assert isinstance(config.db, DbConfig)
    assert config.db.host == "localhost"
    assert config.db.port == 3306
    assert config.debug is True


def test_provide_config_pydantic_model_with_defaults():
    """Test that Pydantic model defaults are applied."""
    config_dict = {"db": {"host": "localhost"}}  # port and debug use defaults

    config = ConfigManagement.provide_config(config_dict, AppConfig)

    assert config.db.port == 5432  # default
    assert config.debug is False  # default


def test_provide_config_empty_with_model():
    """Test provide_config with empty dict and model that has all defaults."""

    class AllDefaultConfig(BaseModel):
        name: str = "app"
        version: str = "1.0.0"

    config = ConfigManagement.provide_config({}, AllDefaultConfig)
    assert config.name == "app"
    assert config.version == "1.0.0"


class TestConfigIntegration:
    """Integration: dependency-injector Configuration with strict+required + strtobool."""

    def _make_container(self, tmp_path, base_ini, override_ini=None):
        (tmp_path / "app.ini").write_text(base_ini)
        if override_ini:
            (tmp_path / "app.develop.ini").write_text(override_ini)

        class C(containers.DeclarativeContainer):
            config = providers.Configuration(strict=True)

        c = C()
        for path in ConfigManagement.get_config_files([tmp_path], default_env="develop"):
            c.config.from_ini(path, required=True)
        return c

    @pytest.mark.parametrize("echo_val,expected", [("false", False), ("true", True)])
    def test_strtobool_as_callback(self, tmp_path, echo_val, expected):
        """as_(strtobool) correctly converts 'false'/'true' from ini."""
        c = self._make_container(tmp_path, f"[db]\necho = {echo_val}\n")
        assert c.config.db.echo.as_(strtobool)() is expected

    def test_strict_rejects_undefined_key(self, tmp_path):
        """strict=True raises on accessing a key not in any loaded file."""
        c = self._make_container(tmp_path, "[db]\nurl = sqlite://\n")
        with pytest.raises(errors.Error, match="Undefined"):
            c.config.db.nonexistent()

    def test_required_rejects_missing_file(self):
        """from_ini(required=True) raises when the file does not exist."""

        class C(containers.DeclarativeContainer):
            config = providers.Configuration(strict=True)

        c = C()
        with pytest.raises(FileNotFoundError):
            c.config.from_ini("/tmp/nonexistent.ini", required=True)

    def test_override_merges_with_strict(self, tmp_path):
        """Base + override merge works under strict mode; override key wins."""
        c = self._make_container(
            tmp_path,
            "[db]\nurl = sqlite://\necho = false\n\n[cache]\nprefix = myapp\n",
            "[db]\necho = true\n",
        )
        assert c.config.db.url() == "sqlite://"
        assert c.config.db.echo.as_(strtobool)() is True
        assert c.config.cache.prefix() == "myapp"


class TestStrictConfig:
    """StrictConfig enforces extra='forbid' and frozen=True."""

    def test_typo_field_rejected(self):
        class DbConfig(StrictConfig):
            url: str
            echo: bool = False

        with pytest.raises(Exception, match="ech0"):
            DbConfig(url="sqlite://", ech0="true")

    def test_immutable_after_creation(self):
        class DbConfig(StrictConfig):
            url: str
            echo: bool = False

        cfg = DbConfig(url="sqlite://")
        with pytest.raises(ValidationError):
            cfg.echo = True
