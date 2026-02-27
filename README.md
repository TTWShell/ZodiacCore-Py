# ZodiacCore-Py

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-e92063.svg)](https://docs.pydantic.dev/)
[![Async First](https://img.shields.io/badge/Async-First-purple.svg)](https://docs.python.org/3/library/asyncio.html)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](https://ttwshell.github.io/ZodiacCore-Py/)
[![PyPI version](https://img.shields.io/pypi/v/zodiac-core.svg)](https://pypi.org/project/zodiac-core/)
[![codecov](https://codecov.io/github/TTWShell/ZodiacCore-Py/graph/badge.svg?token=ZVSMW38NIA)](https://codecov.io/github/TTWShell/ZodiacCore-Py)
[![License](https://img.shields.io/:license-mit-blue.svg)](https://opensource.org/licenses/MIT)

> **The opinionated, async-first core library for modern Python web services.**

## 🎯 Mission

**Stop copy-pasting your infrastructure code.**

Every new FastAPI project starts the same way: setting up logging, error handling, database sessions, pagination... It's tedious, error-prone, and inconsistent across teams.

**ZodiacCore** solves this in two ways: a **library** you drop into any FastAPI app, and a **CLI** that scaffolds a full project so you can start coding in seconds.

## ✨ Key Features

*   **🔍 Observability First**: Built-in JSON structured logging with **Trace ID** injection across the entire request lifecycle (Middleware → Context → Log).
*   **🛡️ Robust Error Handling**: Centralized exception handlers that map `ZodiacException` to standard HTTP 4xx/5xx JSON responses.
*   **💾 Database Abstraction**: Async SQLAlchemy session management and `BaseSQLRepository` with pagination helpers (`paginate_query`).
*   **🎁 Standard Response Wrapper**: Automatic wrapping of API responses into `code` / `data` / `message` via `APIRouter`.
*   **📄 Standard Pagination**: `PageParams` and `PagedResponse[T]` with repository integration.
*   **⚡ Async Ready**: Python 3.12+ async/await from the ground up.
*   **⌨️ zodiac CLI**: Scaffold a 3-tier FastAPI project (DI, routers, config) with one command.

## 📦 Quick Install

| Use case | Install |
|----------|--------|
| **Library only** (use in your app) | `uv add zodiac-core` |
| **Library + CLI** (scaffold new projects) | `uv add "zodiac-core[zodiac]"` |

Extras (combinable): `zodiac-core[sql]` (SQLModel), `zodiac-core[mongo]` (Motor, helpers planned), `zodiac-core[zodiac]` (CLI). See the [Installation Guide](https://ttwshell.github.io/ZodiacCore-Py/user-guide/installation/) for details.

---

## 🚀 Two ways to use ZodiacCore

### 1. Scaffolding (fastest start)

Use the **zodiac** CLI to generate a full project: 3-tier architecture, dependency injection, config, and tests.

> **Note**: `dfd-service` below is the name of the new project you want to create; replace it with your own.

```bash
mkdir dfd-service
cd dfd-service
uv init --python 3.12
uv venv

uv add "zodiac-core[zodiac,sql]"
zodiac new dfd-service --tpl standard-3tier -o .. --force

uv add "fastapi[standard]" --dev
uv run fastapi run --reload
```

Open `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/api/v1/health`. See [Getting started](https://ttwshell.github.io/ZodiacCore-Py/user-guide/getting-started/) and [CLI docs](https://ttwshell.github.io/ZodiacCore-Py/user-guide/cli/).

### 2. Library (use in your own app)

Add **zodiac-core** to an existing FastAPI project and wire up logging, middleware, and response wrapping.

```python
from fastapi import FastAPI
from zodiac_core.routing import APIRouter
from zodiac_core.logging import setup_loguru
from zodiac_core.middleware import register_middleware
from zodiac_core.exception_handlers import register_exception_handlers
from zodiac_core.exceptions import NotFoundException
from loguru import logger

setup_loguru(level="INFO", json_format=True)
app = FastAPI()
register_middleware(app)
register_exception_handlers(app)

router = APIRouter()
@router.get("/items/{item_id}")
async def read_item(item_id: int):
    logger.info(f"request: item_id={item_id}")
    if item_id == 0:
        raise NotFoundException(message="Item not found")
    return {"item_id": item_id}
app.include_router(router)
```

## 📚 Documentation

- **Online**: [https://ttwshell.github.io/ZodiacCore-Py/](https://ttwshell.github.io/ZodiacCore-Py/) (multiple versions via release).
- **Local**: `make docs-serve` (sources in `docs/`).

## 🤝 Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and workflow.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
