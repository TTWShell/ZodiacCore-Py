---
name: zodiac-docs
description: |
  Look up version-matched ZodiacCore docs, source, and tests before writing or
  explaining ZodiacCore-backed APIs, and when the user asks how to use,
  migrate, troubleshoot, or verify ZodiacCore behavior (including 开发API,
  加路由, 写 schema, 抛异常). Do not use for adoption matrices or mechanical
  wiring fixes; use zodiac-core-integration-summary.
---

# Zodiac Docs

Answer ZodiacCore questions and implement ZodiacCore-backed APIs against the
version the user is actually using. Treat documentation, source, tests, and
generated templates as complementary evidence rather than assuming that the
current branch describes every release.

## Resolve The Context

Run the bundled resolver before researching unless the version and source
context have already been verified:

```bash
python3 <skill-directory>/scripts/resolve-zodiac-context.py --path <working-directory>
```

Use the result as follows:

- For `source-tree`, treat that checkout as the primary source. State the
  revision or exact release tag when the distinction matters.
- For `downstream`, use an exact version found by the resolver. Treat a
  dependency constraint as context only; do not choose a release from it or
  present `/latest/` as version-matched documentation.
- For `remote`, ask for a version only when the answer materially differs by
  release. Otherwise use the current published docs and say that the answer is
  for the current release.
- Use `https://ttwshell.github.io/ZodiacCore-Py/<version>/` for an exact
  released version. Use `/latest/` only for explicit latest/current questions
  or after the user chooses it as a fallback.
- Never answer a pinned older-version question solely from the current source
  branch.

## Handle Unresolved Context

Keep version detection intentionally bounded. Do not build an exhaustive
resolver for every workspace, conditional lock, generated requirements, or
custom dependency layout.

Continue when the available evidence is sufficient or the answer does not
depend on a specific release. Otherwise stop before guessing and ask the user
to provide one of:

- the exact installed ZodiacCore version;
- the relevant lock file, source checkout, or fork revision;
- permission to answer against the current published release.

If versioned documentation is unavailable, try the matching Git tag or local
source. If neither provides enough evidence, explain what is missing and ask
the user which source or version to use. Never silently substitute `latest` or
a nearby release.

## Route The Question

Read [references/source-map.md](references/source-map.md) after identifying the
topic. Follow its paths and search terms rather than loading the whole
repository.

Use this evidence order:

1. Read the matching user guide or API documentation for intended usage.
2. Inspect public definitions in `zodiac_core/` for signatures, defaults, and
   implementation behavior.
3. Inspect focused tests for observable contracts and edge cases.
4. Inspect `zodiac/templates/` and `zodiac/commands/` for scaffolding and CLI
   questions.
5. Inspect `CHANGELOG.md`, tags, and diffs for release or migration questions.

Prefer `rg` and `rg --files` for local discovery. When the matching source is
not available locally, browse only the official ZodiacCore GitHub Pages site
and the `TTWShell/ZodiacCore-Py` GitHub repository.

Do not infer runtime guarantees from docs alone when focused source or tests
are available. Distinguish a documented recommendation from behavior enforced
by code.

## Answer Or Implement

For an explanation or review:

- Lead with the direct answer.
- Name the resolved ZodiacCore version or source revision when it affects the
  conclusion.
- Cite the smallest useful set of local files or official documentation pages.
- Call out version uncertainty or a docs/source mismatch explicitly.

For an implementation request, including adding or changing APIs, routes,
schemas, envelopes, pagination, exceptions, HTTP clients, middleware, or
database sessions:

- Resolve the version first.
- Identify the topics and read the matching [source-map](references/source-map.md)
  documentation rows **before editing code**. Do not implement from memory or
  from a copied snippet in the service repo.
- Then inspect the target project's existing style and use only APIs available
  in the resolved version.
- Do not upgrade ZodiacCore or rewrite project architecture unless requested.
- Make the requested change and run focused verification.
- After wiring, envelope, exception, session, HTTP client, or bootstrap
  changes, run `uv run zodiac check --format json` when the project's version
  supports it; otherwise suggest upgrading `zodiac-core` and installing
  `zodiac-core[zodiac]` into dev dependencies.

Remain read-only for questions, diagnoses, and reviews unless the user also
asks for code changes.

## Keep The Boundary Clear

Use `zodiac-core-integration-summary` instead when the requested output is a
service adoption matrix, feature checklist, 对接表, ✅/❌ integration audit,
or a fix loop driven by `zodiac check --format json`. Use this skill to
explain individual ZodiacCore capabilities or help apply them.
