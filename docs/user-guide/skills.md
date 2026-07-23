# Codex Skills

ZodiacCore publishes Codex skills for developers building services with
ZodiacCore. These skills are project assistance files, not runtime Python
dependencies. Install them into the service project where Codex will work.

## Available Skills

| Skill | Purpose |
|-------|---------|
| `zodiac-docs` | Answer version-aware ZodiacCore usage, API, CLI, template, migration, and troubleshooting questions. |
| `zodiac-core-integration-summary` | Audit an existing service and produce a ZodiacCore adoption matrix. |

## Install Into A Project

Codex discovers project skills from `.agents/skills/`. If ZodiacCore-Py is
already checked out locally, copy either skill from the repository:

```bash
mkdir -p .agents/skills
cp -R ~/open-source/ZodiacCore-Py/skills/zodiac-docs .agents/skills/
```

To install from GitHub, first obtain a shallow checkout and then copy the skill
directory:

```bash
git clone --depth 1 https://github.com/TTWShell/ZodiacCore-Py.git /tmp/ZodiacCore-Py
mkdir -p .agents/skills
cp -R /tmp/ZodiacCore-Py/skills/zodiac-docs .agents/skills/
```

Replace `zodiac-docs` with `zodiac-core-integration-summary` to install the
audit skill.

The target project should then contain:

```text
.agents/
  skills/
    zodiac-docs/
      SKILL.md
      agents/
      references/
      scripts/
```

Start a new Codex session in that project, or reload the session if your Codex
client requires it, then ask for the skill by name:

```text
$zodiac-docs
```

## When To Use

Use `zodiac-docs` for questions about ZodiacCore APIs, configuration, CLI,
generated templates, upgrades, and runtime behavior. It resolves the local
source revision or the downstream project's locked ZodiacCore version, then
uses matching documentation, source, and tests as evidence.

Use `zodiac-core-integration-summary` when you want Codex to inspect a service
and produce a compact table showing whether it uses ZodiacCore routing,
exception handling, middleware, logging, HTTP clients, pagination, cache,
database, configuration, schema, and sub-application conventions.

Both skills are read-only by default. They should not modify code unless you
explicitly ask Codex to implement or fix something.
