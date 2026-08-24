# Developer Skills

ZodiacCore publishes skills for developers building services with ZodiacCore.
These files are project assistance for coding agents, not runtime Python
dependencies. Install them into the service project where the agent will work.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `zodiac-docs` | Answer version-aware ZodiacCore usage, API, CLI, template, migration, and troubleshooting questions. |
| `zodiac-core-integration-summary` | Audit a service and produce a ZodiacCore adoption matrix. Mechanical wiring evidence comes from `zodiac check --format json`. |

`zodiac-core-integration-summary` must not restate CLI rule catalogs. It runs
`zodiac check` for anti-patterns, then judges pagination, cache, configuration,
schemas, and ➖/❓. If the user asks to fix mechanical ❌ cells, apply each
error rule's `change` and rerun the CLI. A green check report certifies
mechanical wiring only. Import-layer anti-patterns are in the CLI; thin
routers, DI, session ownership, and lifecycle judgment stay in `AGENTS.md`.

Use `zodiac-docs` to explain an API or version-specific behavior.

## Install Into A Project

Agents commonly discover project skills from `.agents/skills/`. Skills ship
inside the installed `zodiac-core` package. After `uv add "zodiac-core[zodiac]"`,
copy from the package tree (the same files as the source checkout):

```bash
mkdir -p .agents/skills
SKILLS="$(python -c 'import pathlib, zodiac; print(pathlib.Path(zodiac.__file__).parent / "skills")')"
cp -R "$SKILLS/zodiac-core-integration-summary" .agents/skills/
```

If ZodiacCore-Py is checked out locally, copy from the source tree instead:

```bash
mkdir -p .agents/skills
cp -R ~/open-source/ZodiacCore-Py/zodiac/skills/zodiac-core-integration-summary .agents/skills/
```

To install from GitHub, first obtain a shallow checkout and then copy the skill
directory:

```bash
git clone --depth 1 https://github.com/TTWShell/ZodiacCore-Py.git /tmp/ZodiacCore-Py
mkdir -p .agents/skills
cp -R /tmp/ZodiacCore-Py/zodiac/skills/zodiac-core-integration-summary .agents/skills/
```

Replace `zodiac-core-integration-summary` with `zodiac-docs` to install that
skill.

The target project should then contain:

```text
.agents/
  skills/
    zodiac-core-integration-summary/
      SKILL.md
```

Start a new agent session in that project, or reload the session if the client
requires it, then ask for the skill by name:

```text
$zodiac-core-integration-summary
```

Generated projects already document `uv run zodiac check` in `AGENTS.md`. The
CLI is the source of truth for mechanical wiring whether or not the skill is
installed.

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
generated templates, upgrades, and runtime behavior. It resolves the local
source revision or the downstream project's locked ZodiacCore version, then
uses matching documentation, source, and tests as evidence.

Both skills are read-only by default. They should not modify code unless you
explicitly ask the agent to implement or fix something. Fixes for mechanical
wiring must follow the CLI `change` field.
