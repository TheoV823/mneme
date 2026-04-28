"""
benchmark_report.py — Format BenchmarkRunner results for terminal, Markdown, and JSON.

Three formatters:
  format_terminal(results) -> str   Pretty terminal table with emoji verdicts
  format_markdown(results) -> str   GitHub-flavoured Markdown table + summary
  format_json(results)     -> str   JSON with summary + per-scenario detail
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from mneme.benchmark import ScenarioResult, ScenarioVerdict


_VERDICT_EMOJI = {
    ScenarioVerdict.PASS: "✅",
    ScenarioVerdict.FAIL: "❌",
    ScenarioVerdict.WEAK: "⚠️",
    ScenarioVerdict.WEAK_RETRIEVAL: "⚠️",
}

_WIDTH = 72


@dataclass
class BenchmarkSummary:
    """Aggregate statistics across a suite run."""
    total: int
    passed: int
    failed: int
    weak: int
    weak_retrieval: int
    pass_rate: float
    by_category: dict[str, dict[str, int]]


def compute_summary(results: list[ScenarioResult]) -> BenchmarkSummary:
    """Compute aggregate statistics from a list of results."""
    passed = sum(1 for r in results if r.verdict == ScenarioVerdict.PASS)
    failed = sum(1 for r in results if r.verdict == ScenarioVerdict.FAIL)
    weak = sum(1 for r in results if r.verdict == ScenarioVerdict.WEAK)
    weak_retrieval = sum(
        1 for r in results if r.verdict == ScenarioVerdict.WEAK_RETRIEVAL
    )
    checkable = passed + failed
    pass_rate = round(passed / checkable, 2) if checkable > 0 else 0.0

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = {"pass": 0, "fail": 0, "total": 0}
        by_category[cat]["total"] += 1
        if r.verdict == ScenarioVerdict.PASS:
            by_category[cat]["pass"] += 1
        elif r.verdict == ScenarioVerdict.FAIL:
            by_category[cat]["fail"] += 1

    return BenchmarkSummary(
        total=len(results),
        passed=passed,
        failed=failed,
        weak=weak,
        weak_retrieval=weak_retrieval,
        pass_rate=pass_rate,
        by_category=by_category,
    )


# ── Terminal ──────────────────────────────────────────────────────────────

def format_terminal(results: list[ScenarioResult]) -> str:
    """Format results as a readable terminal report."""
    lines: list[str] = []
    lines.append("=" * _WIDTH)
    lines.append("  Mneme Benchmark Report")
    lines.append("=" * _WIDTH)
    lines.append("")

    for r in results:
        emoji = _VERDICT_EMOJI.get(r.verdict, "?")
        lines.append(f"  {emoji} {r.verdict.value:<5}  {r.name}")
        lines.append(f"         {r.explanation}")
        if r.baseline_triggers:
            lines.append(
                f"         baseline triggered: {', '.join(r.baseline_triggers[:4])}"
            )
        lines.append("")

    s = compute_summary(results)
    lines.append("-" * _WIDTH)
    lines.append(
        f"  Summary: {s.passed}/{s.passed + s.failed} violations caught"
        + (
            f"  ({s.weak} weak, {s.weak_retrieval} weak-retrieval)"
            if s.weak or s.weak_retrieval
            else ""
        )
    )
    lines.append(f"  Pass rate: {s.pass_rate:.0%}")
    if s.by_category:
        lines.append("")
        lines.append("  By category:")
        for cat, counts in sorted(s.by_category.items()):
            lines.append(f"    {cat}: {counts['pass']}/{counts['total']} PASS")
    lines.append("=" * _WIDTH)

    return "\n".join(lines)


# ── Markdown ──────────────────────────────────────────────────────────────

def format_markdown(results: list[ScenarioResult]) -> str:
    """Format results as a GitHub-flavoured Markdown report."""
    lines: list[str] = []
    lines.append("## Mneme Benchmark Results")
    lines.append("")
    lines.append("| Scenario | Verdict | Baseline violations | Enhanced violations | Notes |")
    lines.append("|---|---|---|---|---|")

    for r in results:
        emoji = _VERDICT_EMOJI.get(r.verdict, "?")
        triggers = ", ".join(r.baseline_triggers[:3]) or "—"
        lines.append(
            f"| {r.name} | {emoji} {r.verdict.value} "
            f"| {r.baseline_violation_count} "
            f"| {r.enhanced_violation_count} "
            f"| {triggers} |"
        )

    s = compute_summary(results)
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"**{s.passed}/{s.passed + s.failed}** violations caught by Mneme "
        f"({s.pass_rate:.0%} pass rate)."
    )
    if s.weak or s.weak_retrieval:
        lines.append(
            f"_{s.weak} WEAK (baseline too soft), "
            f"{s.weak_retrieval} WEAK_RETRIEVAL (retrieval missed target)._"
        )
    if s.by_category:
        lines.append("")
        lines.append("**By category:**")
        lines.append("")
        for cat, counts in sorted(s.by_category.items()):
            lines.append(f"- **{cat}**: {counts['pass']}/{counts['total']} PASS")

    return "\n".join(lines)


# ── JSON ──────────────────────────────────────────────────────────────────

def format_json(results: list[ScenarioResult]) -> str:
    """Format results as a JSON string suitable for CI or dashboards."""
    s = compute_summary(results)
    payload = {
        "summary": {
            "total": s.total,
            "passed": s.passed,
            "failed": s.failed,
            "weak": s.weak,
            "weak_retrieval": s.weak_retrieval,
            "pass_rate": s.pass_rate,
            "by_category": s.by_category,
        },
        "results": [
            {
                "name": r.name,
                "verdict": r.verdict.value,
                "baseline_violation_count": r.baseline_violation_count,
                "enhanced_violation_count": r.enhanced_violation_count,
                "baseline_triggers": r.baseline_triggers,
                "enhanced_triggers": r.enhanced_triggers,
                "explanation": r.explanation,
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)
