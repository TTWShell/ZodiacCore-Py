# ZodiacCore-Py

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-e92063.svg?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/Async-First-purple.svg?style=for-the-badge" alt="Async First">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="MIT License">
</p>

> **The opinionated, async-first core library for modern Python web services.**

## 🎯 Mission

**Stop copy-pasting your infrastructure code.**

Every new FastAPI project starts the same way: setting up logging, error handling, database sessions, pagination... It's tedious, error-prone, and inconsistent across teams.

**ZodiacCore** solves this by providing a standardized, production-ready foundation. It encapsulates the "boring but critical" components so you can focus 100% on business logic.

## ✨ Key Features

*   **🔍 Observability First**: Built-in JSON structured logging with **Trace ID** injection across the entire request lifecycle (Middleware -> Context -> Log).
*   **🛡️ Robust Error Handling**: Centralized exception handlers that automatically map business exceptions (`ZodiacException`) to standard HTTP 4xx/5xx JSON responses.
*   **💾 Database Abstraction**: Lightweight async SQLAlchemy session management with context vars support (`BaseSQLRepository`).
*   **🎁 Standard Response Wrapper**: Automatic wrapping of all API responses into a consistent JSON structure (`code`, `data`, `message`) via `APIRouter`.
*   **📄 Standard Pagination**: Drop-in Pydantic models for request parameters (`PageParams`) and responses (`PagedResponse`).
*   **⚡ Async Ready**: Designed from the ground up for Python 3.12+ async/await ecosystems.
*   **⌨️ zodiac**: CLI for project scaffolding.

## 📦 Quick Install

**zodiac-core** is the library; the **zodiac** CLI is an optional extra. Use the library in your project when building an app; add the **zodiac** extra when you need the `zodiac` command (e.g. to scaffold new projects).

| Use case | Install |
|----------|--------|
| Library only (in your project) | `uv add zodiac-core` |
| Library + CLI (e.g. global or dev) | `uv add "zodiac-core[zodiac]"` |

More extras (can be combined):

```bash
uv add "zodiac-core[sql]"      # SQL (SQLModel)
uv add "zodiac-core[mongo]"    # MongoDB (motor)
uv add "zodiac-core[zodiac]"   # CLI (zodiac command)
```

For detailed installation instructions, please refer to the **Installation Guide** in the documentation.

## 🚀 Usage at a Glance

```python
from fastapi import FastAPI
from zodiac_core.routing import APIRouter
from zodiac_core.logging import setup_loguru
from zodiac_core.middleware import register_middleware
from zodiac_core.exception_handlers import register_exception_handlers
from zodiac_core.exceptions import NotFoundException
from loguru import logger

# 1. Initialize Standard Logging
setup_loguru(level="INFO", json_format=True)

app = FastAPI()

# 2. Register Middleware & Error Handlers
register_middleware(app)
register_exception_handlers(app)

# 3. Use Zodiac APIRouter (Automatic response wrapping)
router = APIRouter()

@router.get("/items/{item_id}")
async def read_item(item_id: int):
    logger.info(f"request: item_id={item_id}")
    if item_id == 0:
        # Raises standard 404 JSON response
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
