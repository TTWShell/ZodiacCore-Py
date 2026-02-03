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
Installs the `motor` extra so you can use the async MongoDB driver in your app. The library does not yet provide built-in MongoDB session or repository helpers; this extra is for dependency convenience.

```bash
uv add "zodiac-core[mongo]"
```

### Multiple Databases
To install support for both SQL and MongoDB:

```bash
uv add "zodiac-core[sql,mongo]"
```

## 3. Installing Everything (For Development)

If you are setting up a development environment or need all features:

```bash
uv sync --all-extras --all-groups
```

## 4. Verifying Installation

You can verify the installed version and importability:

```python
python -c "import zodiac_core; print(zodiac_core.__version__)"
```
