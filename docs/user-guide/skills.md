# Codex Skills

ZodiacCore publishes Codex skills for developers building services with
ZodiacCore. These skills are project assistance files, not runtime Python
dependencies. Install them into the service project where Codex will work.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `zodiac-core-integration-summary` | Audit an existing service and produce a ZodiacCore adoption matrix. |

## Install Into A Project

From the root of your service project, download the skill into
`.codex/skills/`:

```bash
mkdir -p .codex/skills/zodiac-core-integration-summary
curl -L \
  https://raw.githubusercontent.com/TTWShell/ZodiacCore-Py/master/skills/zodiac-core-integration-summary/SKILL.md \
  -o .codex/skills/zodiac-core-integration-summary/SKILL.md
```

If you already have ZodiacCore-Py checked out locally, copying the directory is
also fine:

```bash
mkdir -p .codex/skills
cp -R ~/open-source/ZodiacCore-Py/skills/zodiac-core-integration-summary .codex/skills/
```

The target project should then contain:

```text
.codex/
  skills/
    zodiac-core-integration-summary/
      SKILL.md
```

Start a new Codex session in that project, or reload the session if your Codex
client requires it, then ask for the skill by name:

```text
$zodiac-core-integration-summary
```

## When To Use

Use `zodiac-core-integration-summary` when you want Codex to inspect a service
and produce a compact table showing whether it uses ZodiacCore routing,
exception handling, middleware, logging, HTTP clients, pagination, cache,
database, configuration, schema, and sub-application conventions.

The skill is read-only by default: it should audit and summarize the project,
not modify code, unless you explicitly ask Codex to fix the findings.
