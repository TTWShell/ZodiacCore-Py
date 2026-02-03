import glob
import os
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import List, Type, TypeVar, Union, overload

from loguru import logger

T = TypeVar("T")


class Environment(str, Enum):
    """
    Supported application environments.
    """

    DEVELOP = "develop"  # Local development
    TESTING = "testing"  # Testing environment
    STAGING = "staging"  # Staging environment (reserved)
    PRODUCTION = "production"  # Production environment


class ConfigManagement:
    """
    Configuration management utility for scanning, loading, and converting configuration files.

    This utility is designed to work well with configuration loading patterns where
    subsequent files override previous ones (e.g., standard `configparser` or
    `dependency-injector`).

    See: https://python-dependency-injector.ets-labs.org/providers/configuration.html
    """

    @staticmethod
    def get_config_files(
        search_paths: List[Union[str, Path]],
        env_var: str = "APPLICATION_ENVIRONMENT",
        default_env: str = "production",
    ) -> List[str]:
        """
        Scans specified directories for configuration files and returns them in loading order.

        The scanning strategy follows these rules:
        1. Base Config: Files with at most one dot (e.g., 'app.ini'). Loaded first.
        2. Env Config: Files matching '{name}.{env}.ini' (e.g., 'app.develop.ini'). Loaded second.

        The returned order (Base -> Env) ensures that environment-specific settings
        override base settings when loaded by configuration providers.

        Files not matching the current environment but belonging to a known Environment enum
        are silently skipped. Files with unknown environment suffixes are logged as debug.

        Args:
            search_paths: List of directory paths to search. **REQUIRED**.
            env_var: Environment variable name to determine current environment.
            default_env: Fallback environment if env_var is not set.

        Returns:
            A list of absolute paths to configuration files, sorted by priority (Base -> Env).

        Example:
            ```python
            from pathlib import Path
            from zodiac_core import ConfigManagement

            # Resolve config path relative to your main application file
            config_dir = Path(__file__).parent / "config"
            files = ConfigManagement.get_config_files(search_paths=[config_dir])
            ```
        """

        target_env = os.environ.get(env_var, default_env).lower()
        base_files = []
        env_files = []

        # Normalize paths
        abs_paths = [Path(p).resolve() for p in search_paths if p]

        # Valid environments set for quick lookup
        valid_envs = {e.value for e in Environment}

        for config_dir in abs_paths:
            if not config_dir.exists():
                continue

            # Get all .ini files and sort them to ensure deterministic order
            ini_files = sorted(glob.glob(str(config_dir / "*.ini")))

            for file_path in ini_files:
                filename = os.path.basename(file_path)

                if ConfigManagement.__is_base_config_file(filename):
                    base_files.append(str(file_path))
                    continue

                # Rule 2: Env Config ({name}.{env}.ini)
                candidate_env = ConfigManagement.__get_configuration_env(filename)

                if candidate_env == target_env:
                    env_files.append(str(file_path))
                elif candidate_env in valid_envs:
                    # Valid environment file, but not for current environment. Skip silently.
                    pass
                else:
                    # Unknown environment or weird format. Log it.
                    logger.debug(f"Ignored config file (unknown env/format): {file_path}")

        return base_files + env_files

    @overload
    @staticmethod
    def provide_config(config: dict) -> SimpleNamespace: ...

    @overload
    @staticmethod
    def provide_config(config: dict, model: Type[T]) -> T: ...

    @staticmethod
    def provide_config(config: dict = None, model: Type[T] = None) -> Union[SimpleNamespace, T]:
        """
        Converts a configuration dictionary into a structured object.

        Supports two modes:
        1. **SimpleNamespace mode** (default): Returns a SimpleNamespace for dot notation access.
        2. **Pydantic model mode**: Pass a Pydantic model class to get type-safe, validated config.

        Args:
            config: The configuration dictionary to convert.
            model: Optional Pydantic model class. If provided, returns an instance of this model.

        Returns:
            SimpleNamespace if no model provided, otherwise an instance of the model.

        Example:
            ```python
            # Mode 1: SimpleNamespace (no type hints, but convenient)
            config = ConfigManagement.provide_config({"db": {"host": "localhost"}})
            print(config.db.host)  # "localhost"

            # Mode 2: Pydantic model (full type hints and validation)
            from pydantic import BaseModel

            class DbConfig(BaseModel):
                host: str
                port: int = 5432

            class AppConfig(BaseModel):
                db: DbConfig

            config = ConfigManagement.provide_config({"db": {"host": "localhost"}}, AppConfig)
            print(config.db.host)  # IDE autocomplete works!
            print(config.db.port)  # 5432 (default value)
            ```
        """
        if config is None:
            config = {}

        # Pydantic model mode: delegate to Pydantic for validation and type coercion
        if model is not None:
            return model(**config)

        # SimpleNamespace mode: recursive conversion
        def _convert(value):
            if isinstance(value, dict):
                return SimpleNamespace(**{k: _convert(v) for k, v in value.items()})
            elif isinstance(value, list):
                return [_convert(item) for item in value]
            return value

        return _convert(config)

    @staticmethod
    def __is_base_config_file(filename: str) -> bool:
        """
        Checks if a filename represents a base configuration file.

        Base files are identified by having one dot in their name.
        """
        return filename.count(".") == 1

    @staticmethod
    def __get_configuration_env(filename: str) -> str:
        """
        Extracts the environment name segment from a configuration filename.

        Expected format: {name}.{env}.ini
        """
        parts = filename.split(".")
        # Caller ensure we have at least 2 dots (split into >= 3 parts)
        # by checking __is_base_config_file first.
        return parts[-2].lower()
