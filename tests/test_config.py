import os
from types import SimpleNamespace

from loguru import logger

from zodiac_core import ConfigManagement, Environment


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
