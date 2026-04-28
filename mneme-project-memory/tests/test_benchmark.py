"""Tests for BenchmarkRunner — scenario loading and PASS/FAIL/WEAK verdicts."""
import json
from pathlib import Path

import pytest

from mneme.benchmark import (
    BenchmarkRunner,
    Scenario,
    ScenarioResult,
    ScenarioVerdict,
    load_scenario,
)
from mneme.memory_store import MemoryStore

FIXTURE_SCENARIO = Path(__file__).parent / "fixtures" / "benchmark_scenario"
EXAMPLE_MEMORY = Path(__file__).parent.parent / "examples" / "project_memory.json"
BENCHMARKS_DIR = Path(__file__).parent.parent / "examples" / "benchmarks"


# ── Scenario loading ───────────────────────────────────────────────────────

def test_load_scenario_reads_all_files():
    s = load_scenario(FIXTURE_SCENARIO)
    assert isinstance(s, Scenario)
    assert "postgres" in s.query.lower()
    assert "sqlalchemy" in s.without_mneme.lower()
    assert "json" in s.with_mneme.lower()
    assert s.metadata["name"] == "test_storage_scenario"


def test_load_scenario_raises_on_missing_file(tmp_path):
    (tmp_path / "query.txt").write_text("test query")
    # without_mneme.txt is missing
    with pytest.raises(FileNotFoundError):
        load_scenario(tmp_path)


# ── ScenarioResult ─────────────────────────────────────────────────────────

def test_scenario_result_has_expected_fields():
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    result = runner.run_scenario(load_scenario(FIXTURE_SCENARIO))
    assert isinstance(result, ScenarioResult)
    assert result.name == "test_storage_scenario"
    assert result.category == "architecture"
    assert isinstance(result.verdict, ScenarioVerdict)
    assert isinstance(result.baseline_violation_count, int)
    assert isinstance(result.enhanced_violation_count, int)
    assert isinstance(result.explanation, str)
    assert isinstance(result.protected_decision_ids_hit, list)


def test_pass_when_baseline_fails_and_enhanced_passes():
    """Baseline triggers violations; enhanced doesn't → PASS."""
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    result = runner.run_scenario(load_scenario(FIXTURE_SCENARIO))
    # The fixture is designed so baseline (postgres/sqlalchemy) triggers
    # violations and enhanced (JSON-only) does not.
    assert result.baseline_violation_count >= 1
    assert result.enhanced_violation_count == 0
    assert result.verdict == ScenarioVerdict.PASS


def test_weak_when_baseline_also_clean(tmp_path):
    """If baseline has no violations either, verdict is WEAK."""
    (tmp_path / "query.txt").write_text("Should we use postgres?")
    (tmp_path / "without_mneme.txt").write_text(
        "Keep using JSON files. No databases needed."  # no violations
    )
    (tmp_path / "with_mneme.txt").write_text(
        "Keep using JSON files. No databases needed."
    )
    (tmp_path / "scenario.json").write_text(json.dumps({
        "name": "weak_scenario",
        "category": "test",
        "description": "Weak — baseline already passes.",
        "expected_failure_terms": ["postgres"],
        "expected_protected_decision_ids": [],
    }))
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    result = runner.run_scenario(load_scenario(tmp_path))
    assert result.verdict == ScenarioVerdict.WEAK


def test_fail_when_enhanced_still_violates(tmp_path):
    """If enhanced response still triggers violations, verdict is FAIL."""
    (tmp_path / "query.txt").write_text("Should we use postgres?")
    (tmp_path / "without_mneme.txt").write_text(
        "Use Postgres. SQLAlchemy migration is the best approach."
    )
    (tmp_path / "with_mneme.txt").write_text(
        "Still recommend Postgres for storage. Add SQLAlchemy ORM."  # still bad
    )
    (tmp_path / "scenario.json").write_text(json.dumps({
        "name": "fail_scenario",
        "category": "test",
        "description": "Enhanced still violates — Mneme failed.",
        "expected_failure_terms": ["postgres"],
        "expected_protected_decision_ids": [],
    }))
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    result = runner.run_scenario(load_scenario(tmp_path))
    assert result.verdict == ScenarioVerdict.FAIL


# ── Run suite ─────────────────────────────────────────────────────────────

def test_run_suite_loads_all_benchmark_scenarios():
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    results = runner.run_suite(BENCHMARKS_DIR)
    assert len(results) == 5
    names = {r.name for r in results}
    assert "storage_backend_violation" in names
    assert "retrieval_complexity_violation" in names


def test_run_suite_all_scenarios_pass():
    """All 5 shipped benchmark scenarios should pass."""
    store = MemoryStore(EXAMPLE_MEMORY)
    store.load()
    runner = BenchmarkRunner(store)
    results = runner.run_suite(BENCHMARKS_DIR)
    failures = [r for r in results if r.verdict != ScenarioVerdict.PASS]
    assert failures == [], (
        f"Expected all scenarios to PASS. Failing: "
        + ", ".join(f"{r.name}={r.verdict}" for r in failures)
    )
