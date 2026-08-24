# zodiac CLI

The **zodiac** command is the CLI for scaffolding Zodiac-based projects. Use the **zodiac** extra when you want the CLI; use **zodiac-core** alone when only the library is needed in a project.

## Install

`uv add` must be run from within a project directory. Create one first with `uv init` if needed (see [Installation](installation.md#about-uv)).

```bash
uv add "zodiac-core[zodiac]"
```

## Commands

- `zodiac --help` — show top-level help and subcommands.
- `zodiac new PROJECT_NAME --tpl TEMPLATE_ID -o OUTPUT_DIR` — generate a new project from a template.
- `zodiac add sub-app NAME` — add a new sub-application skeleton to an existing `sub-applications` project.
- `zodiac check [PATH]` — verify a ZodiacCore service against the wiring contract.
- `zodiac skills install [PATH]` — link packaged agent skills into the project. Defaults to Codex (`.agents/skills`); `--agent` selects Claude, Cursor, Copilot, Gemini, or all.

## Options (zodiac new)

| Argument / Option | Required | Description |
|-------------------|----------|-------------|
| `PROJECT_NAME`    | Yes      | Name of the project. |
| `--tpl` / `template` | Yes  | Template id. Currently supported: `standard-3tier`, `sub-applications`. |
| `-o` / `--output` | Yes      | Directory where the project will be generated. |
| `-f` / `--force` | No       | Allow generation into an existing target directory without removing unrelated files. |
| `--package-name` | No       | Python package name generated inside the project. Defaults to `app`. |

## Options (zodiac add sub-app)

| Argument / Option | Required | Description |
|-------------------|----------|-------------|
| `NAME`            | Yes      | Sub-application service name, for example `billing`. |
| `--resource`      | No       | Example resource name generated inside the sub-application. Defaults to `item`. |
| `--resource-plural` | No     | Override the automatically inferred plural used in routes and function names. |
| `-f` / `--force`  | No       | Overwrite generated files if they already exist. |

## Example

Generate a standard single-app 3-tier project:

```bash
zodiac new my_app --tpl standard-3tier -o ./projects
```

This creates `./projects/my_app/`. Next steps include `uv sync --extra dev`
and `uv run zodiac skills install` (Codex by default; pass `--agent` for
Claude, Cursor, Copilot, Gemini, or all). For the full scaffold-from-scratch
flow, see [Getting Started](getting-started.md).

Generate a parent server with mounted `users` and `orders` sub-applications:

```bash
zodiac new my_subapps --tpl sub-applications -o ./projects
```

This creates `./projects/my_subapps/` with shared parent-owned database/cache setup and independent mounted service apps.

Add a new mounted sub-application to an existing `sub-applications` project:

```bash
cd ./projects/my_subapps
uv sync --extra dev
uv run zodiac add sub-app billing
```

This generates `app/billing/` and `tests/billing/`, but it does not modify
`main.py`. The command prints the import, lifespan, and mount statements that a
developer or coding agent should add after reviewing the current parent app.
The command identifies the generated package from `pyproject.toml` and verifies
the mounted-application structure in `main.py`.
Plural resource names are inferred automatically, including irregular forms:

```bash
uv run zodiac add sub-app catalog --resource category
```

Use `--resource-plural` when the API needs a domain-specific form:

```bash
uv run zodiac add sub-app directory \
  --resource person \
  --resource-plural persons
```

To use the CLI without installing development dependencies, run it as a
one-shot tool instead:

```bash
uvx --from "zodiac-core[zodiac]" zodiac add sub-app billing
```

To customize the generated Python package name:

```bash
zodiac new my_app --tpl standard-3tier -o ./projects --package-name my_service
```

## zodiac skills install

Link the agent skills shipped in the installed `zodiac-core` wheel into the
service project. Skills stay version-matched with the lockfile; they are not
copied into git.

```bash
uv run zodiac skills install
uv run zodiac skills install --agent claude
uv run zodiac skills install --agent claude --agent copilot
uv run zodiac skills install --agent all
uv run zodiac skills install --force
```

Run it from a service root, from a subdirectory inside that project, or pass
PATH. The command walks up to the directory that contains `pyproject.toml` and
links skills there. Defaults to Codex (`.agents/skills`). Other project
directories: Claude `.claude/skills`, Cursor `.cursor/skills`, Copilot
`.github/skills`, Gemini `.gemini/skills`. Unix creates a directory symlink.
Windows creates a directory junction (`mklink /J`) and does not require
Administrator. If linking fails, the command prints OS-specific next steps
instead of copying files. Re-run after `uv sync`; stale links are retargeted
to the current package without `--force`. Use `--force` only to replace a
copied skill directory. Packaged `zodiac-*` skills are added to `.gitignore`.

## zodiac check

`zodiac check` verifies a service that depends on `zodiac-core`. Layout (`standard-3tier`, `sub-applications`, or a generic service) is classified afterwards so specialized rules can apply; a different package shape is still checked. The application entry may be `main.py` or `<package>/main.py`. It parses Python with the AST, so it looks at imports and calls rather than scanning source as text.

It is intentionally a linter for **wrong core wiring**, not a full adoption audit. It flags known anti-patterns and missing bootstrap calls, and each finding includes the contract that was broken plus the required change. It does not rewrite files.

Run it from a service root, from a subdirectory inside that project, or pass PATH:

```bash
uv sync --extra dev
uv run zodiac check
uv run zodiac check --format json
uvx --from "zodiac-core[zodiac]" zodiac check /path/to/project
```

Generated `standard-3tier` and `sub-applications` projects include `zodiac-core[zodiac]` in the development extra so `uv run zodiac check` works after `uv sync --extra dev`. A freshly generated project must pass. Virtualenvs (including directories with `pyvenv.cfg`) and `alembic/` trees are skipped.

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | No contract errors |
| `1` | One or more errors, or PATH is not a ZodiacCore service project |

Output is grouped by rule. `contract`, `change`, and `docs` appear once per rule; each hit is a path, line, and the matching source. `--format json` uses the same grouping (`rules[].count` plus `rules[].hits`) so tools can tally violations without repeating the rule text.

Current checks:

- Envelope routes must use `zodiac_core.routing.APIRouter`, not FastAPI's router. Actually constructing a router with FastAPI's `APIRouter` is an error; an unused FastAPI `APIRouter` import is a warning.
- Business errors must raise `ZodiacException` subclasses, not `HTTPException`.
- Named database dependencies must not wrap `get_session` with `functools.partial`, and must not pass the `session_dependency` factory itself to `Depends`.
- Downstream HTTP clients must use `ZodiacClient` / `ZodiacSyncClient` rather than raw `httpx`, including module-qualified and imported shortcuts such as `httpx.get(...)` or `from httpx import get; get(...)`.
- API routers must not import infrastructure; application services must not import API schemas.
- Process setup must call `setup_loguru()` and `register_exception_handlers(app)`.
- `standard-3tier` must register middleware on the process app; mounted sub-applications register middleware themselves and must not call `setup_loguru()`.

It does **not** decide whether pagination, cache, or a custom config layout should exist. Those remain project choices.

## Templates

- `standard-3tier` uses a single FastAPI app with 3-tier layered architecture and dependency injection. See [Getting Started](getting-started.md) or [Architecture Guide](architecture.md) for details.
- `sub-applications` generates a parent FastAPI server that mounts independent `users` and `orders` sub-applications. See [Sub Applications](sub-applications.md) for multi-app lifecycle, middleware, logging, database, and cache rules.
