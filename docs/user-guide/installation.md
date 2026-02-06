# Installation Guide

ZodiacCore is designed to be modular. You can install only what you need.

## Prerequisites

- **Python**: 3.12 or higher
- **Package Manager**: `pip` (standard) or `uv` (recommended for performance)

## 1. Basic Installation

For a minimal setup (Core utilities, Logging, Exception Handling, Middleware, ...):

```bash
uv add zodiac-core
```

## 2. Installing with Database Support

ZodiacCore separates database dependencies to keep the core lightweight. You can choose to install a single database backend or multiple backends simultaneously.

### SQL Support (SQLAlchemy + SQLModel)
To use SQL databases, you must install the `sql` extra along with the appropriate **async database driver** for your specific database.

```bash
# 1. Install SQL support
uv add "zodiac-core[sql]"

# 2. Install preferred async driver (Examples)
uv add asyncpg       # For PostgreSQL
uv add aiosqlite     # For SQLite
uv add aiomysql      # For MySQL
```

### MongoDB Support (Motor)
Installs the `motor` extra so you can use the async MongoDB driver in your app. **Built-in MongoDB session and repository helpers are planned for a future release.** For now, this extra is for dependency convenience when you integrate Motor directly.

```bash
uv add "zodiac-core[mongo]"
```

### Multiple Databases
To install support for both SQL and MongoDB:

```bash
uv add "zodiac-core[sql,mongo]"
```

### CLI (zodiac command)
To use the **zodiac** CLI for scaffolding projects:

```bash
uv add "zodiac-core[zodiac]"
```

Then run `zodiac --help`. See [zodiac CLI](cli.md) for usage.

## 3. Installing Everything (For Development)

If you are setting up a development environment or need all features:

```bash
uv sync --all-extras --all-groups
```

## 4. Local development (editable install)

When developing the repo locally, install in **editable** mode so code changes take effect without reinstalling. To run the **zodiac** CLI while developing, include the **zodiac** extra:

```bash
uv pip install -e ".[zodiac]"
```

Then `zodiac --help` and `zodiac new ...` use the local code. To add dev/test/docs deps:

```bash
uv sync --all-extras --all-groups
```

## 5. Verifying Installation

You can verify the installed version and importability:

```python
python -c "import zodiac_core; print(zodiac_core.__version__)"
```

To verify the CLI (after installing with the zodiac extra):

```bash
zodiac --help
```
