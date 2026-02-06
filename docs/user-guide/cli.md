# zodiac CLI

The **zodiac** command is the CLI for scaffolding Zodiac-based projects. Use the **zodiac** extra when you want the CLI; use **zodiac-core** alone when only the library is needed in a project.

## Install

To use the CLI:

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
| `--tpl` / `template` | Yes  | Template id. Currently supported: `standard-3tier`. |
| `-o` / `--output` | Yes      | Directory where the project will be generated. |
| `-f` / `--force` | No       | Overwrite files in the target directory if it exists. |

## Example

```bash
zodiac new my_app --tpl standard-3tier -o ./projects
```

## Generated Project Architecture

The `standard-3tier` template generates a project following the **Standard 3-Tier Layered Architecture** with **Dependency Injection**:

- **API (Presentation)**: FastAPI routers and request/response handling
- **Application (Logic)**: Business logic and use case orchestration
- **Infrastructure (Implementation)**: Database models, repositories, and external integrations

The project uses `dependency-injector` for managing component dependencies, providing a clean separation of concerns and making the codebase more testable and maintainable.

> **Note**: While the template uses a 3-tier architecture, ZodiacCore supports flexible layered architectures. You can extend it to a 4-tier architecture with a Domain layer when needed. See the [Architecture Guide](architecture.md) for detailed information.
