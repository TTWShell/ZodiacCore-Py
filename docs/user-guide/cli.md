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

This creates `./projects/my_app/`. For the full scaffold-from-scratch flow (init → add → generate → run), see [Getting Started](getting-started.md).

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

## Templates

- `standard-3tier` uses a single FastAPI app with 3-tier layered architecture and dependency injection. See [Getting Started](getting-started.md) or [Architecture Guide](architecture.md) for details.
- `sub-applications` generates a parent FastAPI server that mounts independent `users` and `orders` sub-applications. See [Sub Applications](sub-applications.md) for multi-app lifecycle, middleware, logging, database, and cache rules.
