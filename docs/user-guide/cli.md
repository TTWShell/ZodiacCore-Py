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
| `--tpl` / `template` | Yes  | Template id. |
| `-o` / `--output` | Yes      | Directory where the project will be generated. |

Example:

```bash
zodiac new my_app --tpl presentation-service-repository -o ./projects
```
