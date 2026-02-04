# Contributing to ZodiacCore-Py

Thanks for your interest in contributing. Please read this guide first.

## Development Environment

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

```bash
# Clone the repo
git clone https://github.com/TTWShell/ZodiacCore-Py.git
cd ZodiacCore-Py

# Install dependencies with uv
uv sync --all-groups
```

## Workflow

1. **Fork** this repo and create a branch (e.g. `feature/xxx` or `fix/xxx`).
2. **Make changes** following the existing style (Ruff config is in `pyproject.toml`).
3. **Verify locally**:
   ```bash
   make lint        # Lint
   make test        # Unit + integration tests
   make docs-build  # Build docs (if you changed them)
   ```
4. **Commit** with clear messages; you may reference issues (e.g. `fix #123`).
5. **Push** to your fork and open a **Pull Request** on GitHub with a short description of the change and motivation.

## Code Style

- Use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting; config is in `pyproject.toml`.
- Add tests in `tests/` for new features when possible, and update `docs/` and `CHANGELOG.md` as needed.

## Documentation

- User docs and API reference live in `docs/`, built with MkDocs.
- Preview locally: `make docs-serve`.
- **Docs release**: On each GitHub Release (published), the workflow **Deploy Docs** builds the docs from that tag and deploys to GitHub Pages via [mike](https://github.com/jimporter/mike). Multiple versions (e.g. `/0.1/`, `/0.2/`, `/latest/`) are available; enable **Settings → Pages → Source: Deploy from branch → gh-pages** once.

## Releases and Versioning

- Version and change history are in [CHANGELOG.md](CHANGELOG.md), following [Semantic Versioning](https://semver.org/).
- Official releases are triggered by GitHub Release; CI builds and publishes to PyPI.

If you have questions, feel free to open an [Issue](https://github.com/TTWShell/ZodiacCore-Py/issues).
