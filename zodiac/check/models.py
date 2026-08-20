"""Values returned by `zodiac check`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """One contract violation and the change that restores the contract."""

    rule_id: str
    severity: str
    path: Path
    line: int
    column: int
    found: str
    contract: str
    change: str
    docs: str


@dataclass(frozen=True)
class CheckResult:
    """Outcome of checking one generated project."""

    project_root: Path
    layout: str
    package_name: str
    file_count: int
    findings: tuple[Finding, ...]

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    @property
    def rule_count(self) -> int:
        return len({finding.rule_id for finding in self.findings})
