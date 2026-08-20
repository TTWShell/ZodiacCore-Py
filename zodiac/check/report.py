"""Text and JSON reports grouped by rule."""

from __future__ import annotations

import json

from zodiac.check.models import CheckResult, Finding


def render_report(result: CheckResult, output_format: str = "text") -> str:
    """Render a check result for humans or tools."""
    if output_format == "json":
        return _render_json(result)
    return _render_text(result)


def group_findings(findings: tuple[Finding, ...]) -> list[tuple[str, tuple[Finding, ...]]]:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.rule_id, []).append(finding)
    return [(rule_id, tuple(items)) for rule_id, items in sorted(grouped.items())]


def _render_text(result: CheckResult) -> str:
    header = f"zodiac check: {result.layout} ({result.file_count} files)"
    if result.ok and not result.findings:
        return f"{header}: passed\n"

    lines = [
        f"{header}: {result.error_count} error(s), {result.warning_count} warning(s), {result.rule_count} rule(s)",
        "",
    ]
    for rule_id, hits in group_findings(result.findings):
        sample = hits[0]
        lines.append(f"{rule_id}  ({len(hits)})")
        lines.append(f"  contract: {sample.contract}")
        lines.append(f"  change:   {sample.change}")
        lines.append(f"  docs:     {sample.docs}")
        for finding in hits:
            location = f"{finding.path.as_posix()}:{finding.line}:{finding.column}"
            lines.append(f"  {location}  {finding.found}")
        lines.append("")
    return "\n".join(lines)


def _render_json(result: CheckResult) -> str:
    payload = {
        "ok": result.ok,
        "layout": result.layout,
        "package_name": result.package_name,
        "project_root": str(result.project_root),
        "file_count": result.file_count,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "rule_count": result.rule_count,
        "rules": [
            {
                "rule_id": rule_id,
                "severity": hits[0].severity,
                "count": len(hits),
                "contract": hits[0].contract,
                "change": hits[0].change,
                "docs": hits[0].docs,
                "hits": [
                    {
                        "path": finding.path.as_posix(),
                        "line": finding.line,
                        "column": finding.column,
                        "found": finding.found,
                    }
                    for finding in hits
                ],
            }
            for rule_id, hits in group_findings(result.findings)
        ],
    }
    return json.dumps(payload, indent=2) + "\n"
