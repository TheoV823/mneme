"""
benchmark.py — Load and run benchmark scenarios for Mneme.

A scenario is a directory containing:
  query.txt         — The question asked of the LLM
  without_mneme.txt — Canned response with no memory injected (baseline)
  with_mneme.txt    — Canned response with memory injected (enhanced)
  scenario.json     — Metadata: name, description, expected_failure_terms

Verdict logic:
  PASS   — baseline has >= 1 violation; enhanced has 0 violations
  FAIL   — enhanced still has >= 1 violation
  WEAK   — baseline has 0 violations (scenario is too weak to prove anything)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from mneme.decision_retriever import DecisionRetriever
from mneme.enforcer import check_prompt
from mneme.memory_store import MemoryStore


class ScenarioVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WEAK = "WEAK"
    WEAK_RETRIEVAL = "WEAK_RETRIEVAL"


@dataclass
class Scenario:
    path: Path
    query: str
    without_mneme: str
    with_mneme: str
    metadata: dict


@dataclass
class ScenarioResult:
    name: str
    category: str
    verdict: ScenarioVerdict
    baseline_violation_count: int
    enhanced_violation_count: int
    explanation: str
    baseline_triggers: list[str] = field(default_factory=list)
    enhanced_triggers: list[str] = field(default_factory=list)
    protected_decision_ids_hit: list[str] = field(default_factory=list)


def load_scenario(path: str | Path) -> Scenario:
    """Load a benchmark scenario from a directory.

    Raises:
        FileNotFoundError: If any required file is missing.
    """
    p = Path(path)
    required = ["query.txt", "without_mneme.txt", "with_mneme.txt", "scenario.json"]
    for fname in required:
        if not (p / fname).exists():
            raise FileNotFoundError(f"Missing required file: {p / fname}")

    return Scenario(
        path=p,
        query=(p / "query.txt").read_text(encoding="utf-8").strip(),
        without_mneme=(p / "without_mneme.txt").read_text(encoding="utf-8").strip(),
        with_mneme=(p / "with_mneme.txt").read_text(encoding="utf-8").strip(),
        metadata=json.loads((p / "scenario.json").read_text(encoding="utf-8")),
    )


class BenchmarkRunner:
    """Evaluates benchmark scenarios against project memory.

    Reuses enforcer.check_prompt() so evaluation is identical to the live product.
    """

    def __init__(self, store: MemoryStore, top: int = 5) -> None:
        self.store = store
        self.retriever = DecisionRetriever(store.decisions())
        self.top = top

    def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        scored = self.retriever.retrieve(scenario.query)

        baseline_result = check_prompt(scenario.without_mneme, scored, top=self.top)
        enhanced_result = check_prompt(scenario.with_mneme, scored, top=self.top)

        baseline_count = len(baseline_result.violations)
        enhanced_count = len(enhanced_result.violations)

        baseline_triggers = [v.trigger for v in baseline_result.violations]
        enhanced_triggers = [v.trigger for v in enhanced_result.violations]

        name = scenario.metadata.get("name", scenario.path.name)
        category = scenario.metadata.get("category", "uncategorised")

        expected_ids: list[str] = scenario.metadata.get(
            "expected_protected_decision_ids", []
        )
        retrieved_ids = {s.decision.id for s in scored if s.score > 0}
        protected_hit = [did for did in expected_ids if did in retrieved_ids]
        intended_decisions_retrieved = (
            not expected_ids or len(protected_hit) == len(expected_ids)
        )

        if baseline_count == 0:
            verdict = ScenarioVerdict.WEAK
            explanation = (
                "Baseline response had no violations — scenario fixtures may be too weak. "
                "Strengthen without_mneme.txt to include more explicit failure terms."
            )
        elif enhanced_count > 0:
            verdict = ScenarioVerdict.FAIL
            explanation = (
                f"Mneme did not prevent the violation. "
                f"Enhanced response still triggered {enhanced_count} violation(s): "
                f"{', '.join(enhanced_triggers[:3])}."
            )
        elif not intended_decisions_retrieved:
            verdict = ScenarioVerdict.WEAK_RETRIEVAL
            missing = [d for d in expected_ids if d not in retrieved_ids]
            explanation = (
                f"Enhanced response was clean, but intended decision(s) were not retrieved: "
                f"{', '.join(missing)}. PASS may be coincidental."
            )
        else:
            verdict = ScenarioVerdict.PASS
            explanation = (
                f"Mneme prevented the violation. "
                f"Baseline triggered {baseline_count} violation(s) "
                f"({', '.join(baseline_triggers[:3])}); "
                f"enhanced response had none. "
                f"Retrieved: {', '.join(protected_hit)}."
            )

        return ScenarioResult(
            name=name,
            category=category,
            verdict=verdict,
            baseline_violation_count=baseline_count,
            enhanced_violation_count=enhanced_count,
            explanation=explanation,
            baseline_triggers=baseline_triggers,
            enhanced_triggers=enhanced_triggers,
            protected_decision_ids_hit=protected_hit,
        )

    def run_suite(self, benchmarks_dir: str | Path) -> list[ScenarioResult]:
        """Run all scenarios found under benchmarks_dir."""
        root = Path(benchmarks_dir)
        scenario_dirs = sorted(
            d for d in root.iterdir()
            if d.is_dir() and (d / "scenario.json").exists()
        )
        return [self.run_scenario(load_scenario(d)) for d in scenario_dirs]
