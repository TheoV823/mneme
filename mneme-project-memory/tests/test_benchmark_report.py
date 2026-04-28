"""Tests for benchmark report output (terminal, Markdown, JSON)."""
import json

from mneme.benchmark import ScenarioResult, ScenarioVerdict
from mneme.benchmark_report import (
    format_terminal,
    format_markdown,
    format_json,
    BenchmarkSummary,
    compute_summary,
)


def _results(verdicts: list[str]) -> list[ScenarioResult]:
    # Alternate categories so by_category tests have something to verify.
    cats = ["architecture", "scope", "anti_pattern"]
    return [
        ScenarioResult(
            name=f"scenario_{i}",
            category=cats[i % len(cats)],
            verdict=ScenarioVerdict(v),
            baseline_violation_count=1 if v not in ("WEAK", "WEAK_RETRIEVAL") else 0,
            enhanced_violation_count=1 if v == "FAIL" else 0,
            explanation=f"Explanation for {v}.",
        )
        for i, v in enumerate(verdicts)
    ]


# ── Summary computation ────────────────────────────────────────────────────

def test_summary_counts_correctly():
    results = _results(["PASS", "PASS", "FAIL", "WEAK"])
    s = compute_summary(results)
    assert isinstance(s, BenchmarkSummary)
    assert s.total == 4
    assert s.passed == 2
    assert s.failed == 1
    assert s.weak == 1


def test_summary_pass_rate():
    results = _results(["PASS", "PASS", "PASS", "FAIL"])
    s = compute_summary(results)
    assert s.pass_rate == 0.75  # 3 of 4


def test_summary_all_pass():
    results = _results(["PASS", "PASS", "PASS"])
    s = compute_summary(results)
    assert s.pass_rate == 1.0


# ── Terminal output ────────────────────────────────────────────────────────

def test_terminal_contains_scenario_names():
    results = _results(["PASS", "FAIL"])
    out = format_terminal(results)
    assert "scenario_0" in out
    assert "scenario_1" in out


def test_terminal_shows_verdict_labels():
    results = _results(["PASS", "FAIL", "WEAK"])
    out = format_terminal(results)
    assert "PASS" in out
    assert "FAIL" in out
    assert "WEAK" in out


def test_terminal_shows_summary_line():
    results = _results(["PASS", "PASS", "FAIL"])
    out = format_terminal(results)
    assert "2/3" in out or "2 / 3" in out


# ── Markdown output ────────────────────────────────────────────────────────

def test_markdown_contains_table():
    results = _results(["PASS", "FAIL"])
    md = format_markdown(results)
    assert "|" in md
    assert "scenario_0" in md


def test_markdown_has_summary_section():
    results = _results(["PASS"])
    md = format_markdown(results)
    assert "## Summary" in md or "**" in md


# ── JSON output ───────────────────────────────────────────────────────────

def test_json_output_is_valid():
    results = _results(["PASS", "FAIL"])
    raw = format_json(results)
    data = json.loads(raw)  # must not raise
    assert "summary" in data
    assert "results" in data


def test_json_contains_all_results():
    results = _results(["PASS", "FAIL", "WEAK"])
    data = json.loads(format_json(results))
    assert len(data["results"]) == 3
    names = {r["name"] for r in data["results"]}
    assert "scenario_0" in names


def test_json_summary_fields():
    results = _results(["PASS", "PASS"])
    data = json.loads(format_json(results))
    s = data["summary"]
    assert s["total"] == 2
    assert s["passed"] == 2
    assert s["pass_rate"] == 1.0
    assert "weak_retrieval" in s
    assert "by_category" in s
