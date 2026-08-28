# Developer Skills

ZodiacCore publishes skills for developers building services with ZodiacCore.
These files are project assistance for coding agents, not runtime Python
dependencies. Install them into the service project where the agent will work.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `zodiac-docs` | Look up version-matched docs, source, and tests before answering usage questions or implementing APIs, routes, schemas, CLI, templates, migrations, and troubleshooting. |
| `zodiac-core-integration-summary` | Audit a service and produce a ZodiacCore adoption matrix. Mechanical wiring evidence comes from `zodiac check --format json`. |

`zodiac-core-integration-summary` must not restate CLI rule catalogs. It runs
`zodiac check` for anti-patterns, then judges pagination, cache, configuration,
schemas, and ➖/❓. If the user asks to fix mechanical ❌ cells, apply each
error rule's `change` and rerun the CLI. A green check report certifies
mechanical wiring only. Import-layer anti-patterns are in the CLI; thin
routers, DI, session ownership, and lifecycle judgment stay in `AGENTS.md`.

Use `zodiac-docs` to explain an API or version-specific behavior, and when
adding or changing routes, schemas, envelopes, pagination, or exceptions.

## Install Into A Project

Agents discover project skills from `.agents/skills/`. Packaged ZodiacCore
skills live in the installed `zodiac-core` wheel. Link them from the version
you actually installed:

```bash
uv add --dev "zodiac-core[zodiac]"
uv run zodiac skills install
```

`zodiac new` prints this after `uv sync --extra dev` so the links follow the
project's locked `zodiac-core`, not the CLI that generated the files. Run it
from the service root or a subdirectory; it walks up to `pyproject.toml`.

Defaults to Codex and links `.agents/skills/zodiac-*` to the matching folder
in the package. Use `--agent` for Claude (`.claude/skills`), Cursor
(`.cursor/skills`), Copilot (`.github/skills`), Gemini (`.gemini/skills`),
or `--agent all`. Unix uses a directory symlink; Windows uses a directory
junction. The command gitignores the packaged `zodiac-*` directories. Re-run
after `uv sync`; existing links to packaged `zodiac-*` skills are retargeted
to the current install. Use `--force` only to replace a copied directory.
Do not copy or commit those directories.

Remove the packaged links with `uv run zodiac skills uninstall` (same `--agent`
and project-root walk-up). Other skills in the directory stay. Use `--force`
only to delete a copied `zodiac-*` directory.

Start a new agent session in that project, or reload the session if the client
requires it, then ask for the skill by name:

```text
$zodiac-core-integration-summary
```

Generated projects document `uv run zodiac skills install` (Codex by default;
pass `--agent` for other clients) and `uv run zodiac check` in `AGENTS.md` and
`README.md`. The CLI is the source of truth for mechanical wiring whether or
not the skill is installed.

## When To Use

Use `zodiac-core-integration-summary` when you want an adoption matrix, 对接表,
or to fix wiring the CLI already reported. Run:

```bash
uv run zodiac check --format json
```

If the project does not install the CLI extra, or the installed `zodiac-core`
predates `zodiac check`, stop and prompt the user to upgrade `zodiac-core` and
add `zodiac-core[zodiac]` to dev dependencies, then rerun. Do not run the
latest CLI from `uvx` against an older project.

Map `rules[]` into the matrix columns, then fill pagination, cache,
configuration, and schemas by reading the code. Apply `change` only when the
user asked to fix mechanical errors.

Use `zodiac-docs` for questions about ZodiacCore APIs, configuration, CLI,
generated templates, upgrades, and runtime behavior, and before implementing
those APIs in a service. It resolves the local source revision or the
downstream project's locked ZodiacCore version, then uses matching
documentation, source, and tests as evidence. Do not implement from memory;
read the skill's source-map rows first.

Both skills are read-only by default. They should not modify code unless you
explicitly ask the agent to implement or fix something. Fixes for mechanical
wiring must follow the CLI `change` field.
