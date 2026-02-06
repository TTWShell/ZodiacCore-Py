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
└── app.production.ini  # Production secrets/tuning
```

### Loading the Config
You can use `ConfigManagement` to find the correct files and then load them using your preferred library (like `configparser` or `dependency-injector`).

```python
from pathlib import Path
from zodiac_core import ConfigManagement

# 1. Get the list of files in correct loading order
config_dir = Path(__file__).parent / "config"
config_files = ConfigManagement.get_config_files(
    search_paths=[config_dir],
    env_var="APPLICATION_ENVIRONMENT",  # Default: APPLICATION_ENVIRONMENT
    default_env="develop"                # Fallback if env_var is missing
)

# Returns: ['.../config/app.ini', '.../config/app.develop.ini']
```

---

## 3. Configuration Objects

ZodiacCore provides two ways to access your configuration data using `ConfigManagement.provide_config`:

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
from zodiac_core import ConfigManagement

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

## 4. API Reference

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
