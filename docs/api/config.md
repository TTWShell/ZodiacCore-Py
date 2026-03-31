# Configuration Management

ZodiacCore provides a robust utility for managing application settings using `.ini` files. It is designed to follow the "Base + Override" pattern, making it ideal for multi-environment deployments (Development, Testing, Production).

## 1. Core Concepts

### Environment-Based Loading
The configuration system automatically detects your current environment (via environment variables) and loads files in a specific order:

1. **Base Config**: Files like `app.ini`. These are loaded first.
2. **Environment Config**: Files like `app.production.ini`. These are loaded second, overriding any matching keys from the base config.

### Dot-Notation Access
Instead of using dictionary keys (e.g., `config['db']['host']`), ZodiacCore can convert your settings into a `SimpleNamespace`, allowing for cleaner dot-notation access (e.g., `config.db.host`).

---

## 2. Setting Up Your Config Folder

A typical production-ready configuration folder structure:

```text
config/
├── app.ini             # Default settings (all environments)
├── app.develop.ini     # Local development overrides
├── app.testing.ini     # Test overrides
└── app.production.ini  # Production secrets/tuning
```

### Loading the Config
You can use `ConfigManagement` to find the correct files and then load them using your preferred library (like `configparser` or `dependency-injector`).

```python
from pathlib import Path
from zodiac_core.config import ConfigManagement

# 1. Get the list of files in correct loading order
config_dir = Path(__file__).parent / "config"
config_files = ConfigManagement.get_config_files(
    search_paths=[config_dir],
    env_var="APPLICATION_ENVIRONMENT",  # Default: APPLICATION_ENVIRONMENT
    default_env="production"            # Default fallback if env_var is missing
)

# For local app templates, you can override the fallback explicitly:
# ConfigManagement.get_config_files(search_paths=[config_dir], default_env="develop")
```

### Integrating with dependency-injector

This is the default integration pattern used by the generated project template.

```python
from distutils.util import strtobool
from pathlib import Path

from dependency_injector import containers, providers
from zodiac_core.config import ConfigManagement


class Container(containers.DeclarativeContainer):
    config = providers.Configuration(strict=True)

    @staticmethod
    def initialize():
        config_dir = Path(__file__).resolve().parent.parent / "config"
        config_files = ConfigManagement.get_config_files(
            search_paths=[config_dir],
            default_env="develop",
        )

        container = Container()
        for path in config_files:
            container.config.from_ini(path, required=True)

        return container


container = Container.initialize()
db_url = container.config.db.url()
db_echo = container.config.db.get("echo", as_=strtobool)
```

### Testing Environment

`testing` is a first-class environment. A common pattern is:

- Keep test overrides in `config/app.testing.ini`
- Set `APPLICATION_ENVIRONMENT=testing` in your test bootstrap
- Let `ConfigManagement.get_config_files()` load `app.ini` first, then `app.testing.ini`

```python
import os

os.environ.setdefault("APPLICATION_ENVIRONMENT", "testing")
```

---

## 3. Configuration Objects

ZodiacCore provides two ways to access your configuration data using `ConfigManagement.provide_config`:

If you are using the generated template or `dependency-injector`, prefer `providers.Configuration()` plus `from_ini(...)` as your main path. `provide_config()` is mainly for projects that want ZodiacCore's config helpers without using DI.

### Mode A: SimpleNamespace (Quick Access)
This mode is useful for rapid prototyping. It converts the dictionary into a `SimpleNamespace`, allowing for dot-notation access but without type hints or validation.

```python
raw_data = {"db": {"host": "localhost", "port": 5432}}
config = ConfigManagement.provide_config(raw_data)

print(config.db.host)  # 'localhost'
```

### Mode B: Pydantic Model (Recommended)
For production applications, it is highly recommended to use a Pydantic model. This provides:

1. **Type Safety**: Full IDE autocompletion and type checking.
2. **Validation**: Runtime checks to ensure your configuration is valid.
3. **Defaults**: Automatically fill in missing values defined in your schema.

```python
from pydantic import BaseModel
from zodiac_core.config import ConfigManagement

class DbConfig(BaseModel):
    host: str
    port: int = 5432

class AppConfig(BaseModel):
    db: DbConfig

raw_data = {"db": {"host": "localhost"}}
# Pass the model class as the second argument
config = ConfigManagement.provide_config(raw_data, AppConfig)

print(config.db.host)  # 'localhost' (with IDE autocomplete!)
print(config.db.port)  # 5432 (default value applied)
```

---

## 4. Best Practices with dependency-injector

> For the full `providers.Configuration` API, see the [official documentation](https://python-dependency-injector.ets-labs.org/providers/configuration.html).

When using `providers.Configuration` from dependency-injector, follow these practices to catch configuration errors early and keep your code type-safe.

### Strict Mode

Always enable `strict=True` on the Configuration provider. Without it, accessing an undefined config key silently returns `None` instead of raising an error — bugs surface at runtime instead of startup.

```python
# Good — typo or missing key raises immediately
config = providers.Configuration(strict=True)

# Bad — config.db.hoost() silently returns None
config = providers.Configuration()
```

### Required Config Files

Pass `required=True` to `from_ini()` for files that must exist. By default, missing files are silently ignored.

```python
for path in config_files:
    container.config.from_ini(path, required=True)
```

### Type Conversion

All values from `.ini` files are strings. Use the built-in helpers or Pydantic models for conversion:

| Need | Approach |
|------|----------|
| Integer | `config.api.timeout.as_int()` |
| Float | `config.api.ratio.as_float()` |
| Bool | `config.db.echo.as_(strtobool)` — **not** `as_(bool)`, since `bool("false")` is `True` |
| Custom | `config.pi.as_(Decimal)` |
| Whole section | `ConfigManagement.provide_config(container.config.db(), DbConfig)` — Pydantic handles all conversions |

The **Pydantic model approach** is recommended for sections with multiple fields — it handles type coercion, validation, and defaults in one place, and you don't need to worry about `strtobool` or `as_int()`:

```python
from pydantic import BaseModel
from zodiac_core.config import ConfigManagement

class DbConfig(BaseModel):
    url: str
    echo: bool = False      # Pydantic correctly parses "false" → False

db_cfg = ConfigManagement.provide_config(container.config.db(), DbConfig)
db.setup(database_url=db_cfg.url, echo=db_cfg.echo)
```

### Environment Variable Interpolation

`.ini` files support `${ENV_VAR}` and `${ENV_VAR:default}` syntax for injecting secrets without hardcoding:

```ini
[db]
url = ${DATABASE_URL:sqlite+aiosqlite:///:memory:}
echo = false
```

To require that all referenced environment variables are defined (no silent empty substitution), pass `envs_required=True`:

```python
container.config.from_ini(path, required=True, envs_required=True)
```

---

## 5. API Reference

### Environment Enum
::: zodiac_core.config.Environment
    options:
      heading_level: 4
      show_root_heading: true

### Configuration Management
::: zodiac_core.config.ConfigManagement
    options:
      heading_level: 4
      show_root_heading: true
      members:
        - get_config_files
        - provide_config
