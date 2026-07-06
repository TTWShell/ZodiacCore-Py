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

## Options (zodiac new)

| Argument / Option | Required | Description |
|-------------------|----------|-------------|
| `PROJECT_NAME`    | Yes      | Name of the project. |
| `--tpl` / `template` | Yes  | Template id. Currently supported: `standard-3tier`, `sub-applications`. |
| `-o` / `--output` | Yes      | Directory where the project will be generated. |
| `-f` / `--force` | No       | Allow generation into an existing target directory without removing unrelated files. |
| `--package-name` | No       | Python package name generated inside the project. Defaults to `app`. |

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

To customize the generated Python package name:

```bash
zodiac new my_app --tpl standard-3tier -o ./projects --package-name my_service
```

## Templates

- `standard-3tier` uses a single FastAPI app with 3-tier layered architecture and dependency injection. See [Getting Started](getting-started.md) or [Architecture Guide](architecture.md) for details.
- `sub-applications` generates a parent FastAPI server that mounts independent `users` and `orders` sub-applications. See [Sub Applications](sub-applications.md) for multi-app lifecycle, middleware, logging, database, and cache rules.
