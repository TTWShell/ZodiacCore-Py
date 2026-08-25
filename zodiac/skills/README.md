# ZodiacCore Developer Skills

This directory contains agent skills for developers building services with
ZodiacCore. These skills are not for maintaining ZodiacCore itself; they encode
project-level practices that downstream service teams can reuse.

## Organization

Keep each skill as a top-level directory under `zodiac/skills/`. The
`zodiac-core` wheel ships only the globs in `pyproject.toml`
(`[tool.setuptools.package-data]`): `SKILL.md`, `agents/*`, `references/*`,
and `scripts/*.py`. This authoring `README.md` stays in git and is not
packaged. When adding a new asset type, update those globs and
`tests/test_build.py`.

```text
zodiac/skills/
  zodiac-docs/
    SKILL.md
    agents/
    references/
    scripts/
  zodiac-core-integration-summary/
    SKILL.md
```

Use a clear ZodiacCore-specific name and keep one skill focused on one
developer task. Avoid nesting skills under extra category directories.

## Recommended Skill Boundaries

- `zodiac-docs`: answer version-aware framework usage, API, CLI, template,
  migration, and troubleshooting questions.
- `zodiac-core-integration-summary`: audit an existing service and produce a
  ZodiacCore adoption matrix. Run `zodiac check --format json` for mechanical
  wiring evidence; keep ➖/❓ and pagination/cache/config/schema judgment here.
  If the user asks to fix CLI errors, apply each rule's `change`.

## Authoring Rules

- Write skills for application developers, not ZodiacCore maintainers.
- Prefer task-oriented guidance over low-level module summaries.
- Include concrete search patterns and acceptance criteria.
- Link to ZodiacCore docs when behavior is defined by the framework.
- Mark optional capabilities as not applicable when a service intentionally
  does not need them.
- Do not copy `zodiac check` rule catalogs into skill prompts. Call the CLI.
