# ZodiacCore Developer Skills

This directory contains Codex skills for developers building services with
ZodiacCore. These skills are not for maintaining ZodiacCore itself; they encode
project-level practices that downstream service teams can reuse.

## Organization

Keep each skill as a top-level directory:

```text
skills/
  zodiac-core-integration-summary/
    SKILL.md
```

Use the `zodiac-core-` prefix for discoverability and keep one skill focused on
one developer task. Avoid nesting skills under category directories because
Codex skill installers commonly expect each skill package to live directly
under `skills/`.

## Recommended Skill Boundaries

- `zodiac-core-integration-summary`: audit an existing service and produce a
  ZodiacCore adoption matrix.

## Authoring Rules

- Write skills for application developers, not ZodiacCore maintainers.
- Prefer task-oriented guidance over low-level module summaries.
- Include concrete search patterns and acceptance criteria.
- Link to ZodiacCore docs when behavior is defined by the framework.
- Mark optional capabilities as not applicable when a service intentionally
  does not need them.
