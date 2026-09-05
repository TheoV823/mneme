"""
adr_diagnostics.py — Shared warn-only ADR diagnostics collection.

Combines ADR freshness issues and lifecycle findings into one deduplicated
list. Consumers (``mneme check``, ``mneme setup``) render these as warnings;
they never influence exit codes or enforcement behavior.
"""

from __future__ import annotations

from pathlib import Path

from mneme.adr_freshness import FreshnessIssue, check_freshness
from mneme.adr_lifecycle import analyze_lifecycle


def collect_adr_diagnostics(
    memory_path: str | Path,
    adr_dir: str | Path,
) -> list[FreshnessIssue]:
    """Collect ADR freshness issues and lifecycle findings (warn-only)."""
    freshness = check_freshness(memory_path=memory_path, adr_dir=adr_dir)
    lifecycle = analyze_lifecycle(corpus_dir=adr_dir, memory_path=memory_path)
    seen: set[tuple[str, str, str]] = set()
    combined: list[FreshnessIssue] = []
    for issue in freshness + lifecycle:
        key = (issue.code, issue.adr_id, issue.path)
        if key not in seen:
            seen.add(key)
            combined.append(issue)
    return combined
