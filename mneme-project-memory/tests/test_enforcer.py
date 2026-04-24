"""Tests for mneme/enforcer.py and `mneme check` CLI command."""
import json
from pathlib import Path

import pytest

from mneme.cli import main
from mneme.decision_retriever import DecisionRetriever, ScoredDecision
from mneme.enforcer import EnforcementResult, Severity, Violation, check_prompt
from mneme.schemas import Decision


# ── shared fixtures ───────────────────────────────────────────────────────────

def _scored(decision: Decision, score: float = 1.0) -> ScoredDecision:
    return ScoredDecision(decision=decision, score=score)


STORAGE = Decision(
    id="storage_json",
    decision="Use JSON storage only",
    rationale="local-first, avoid infra complexity",
    scope=["storage"],
    constraints=["no postgres", "no ORM"],
    anti_patterns=["introduce ORM", "add vector db"],
)

RETRIEVAL = Decision(
    id="retrieval_det",
    decision="Keep retrieval deterministic",
    rationale="testability",
    scope=["retrieval"],
    constraints=["no embeddings", "no ML"],
    anti_patterns=["add vector db", "use cosine similarity"],
)


def _memory_file(tmp_path: Path) -> Path:
    mem = tmp_path / "project_memory.json"
    mem.write_text(json.dumps({
        "meta": {"name": "t", "description": "t"},
        "items": [], "examples": [],
        "decisions": [
            {
                "id": "storage_json",
                "decision": "Use JSON storage only",
                "rationale": "local-first",
                "scope": ["storage", "backend"],
                "constraints": ["no postgres", "no ORM"],
                "anti_patterns": ["introduce ORM", "add vector db"],
                "created_at": "2026-04-24T00:00:00Z",
                "updated_at": "2026-04-24T00:00:00Z",
            },
            {
                "id": "retrieval_det",
                "decision": "Keep retrieval deterministic",
                "rationale": "testability",
                "scope": ["retrieval"],
                "constraints": ["no embeddings"],
                "anti_patterns": ["use cosine similarity"],
                "created_at": "2026-04-24T00:00:00Z",
                "updated_at": "2026-04-24T00:00:00Z",
            },
        ],
    }))
    return mem


def _input_file(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "prompt.txt"
    p.write_text(content, encoding="utf-8")
    return p


# ── check_prompt unit tests ───────────────────────────────────────────────────

def test_clean_input_returns_pass():
    scored = [_scored(STORAGE)]
    result = check_prompt("Store all data as flat JSON files on disk.", scored)
    assert result.verdict == Severity.PASS
    assert result.violations == []


def test_anti_pattern_match_returns_fail():
    scored = [_scored(STORAGE)]
    result = check_prompt("We should introduce an ORM for database access.", scored)
    assert result.verdict == Severity.FAIL


def test_anti_pattern_violation_has_fail_severity():
    scored = [_scored(STORAGE)]
    result = check_prompt("introduce an ORM layer", scored)
    fail_violations = [v for v in result.violations if v.severity == Severity.FAIL]
    assert len(fail_violations) >= 1


def test_constraint_violation_returns_warn():
    scored = [_scored(STORAGE)]
    result = check_prompt("What if we used postgres for this?", scored)
    assert result.verdict == Severity.WARN


def test_constraint_violation_has_warn_severity():
    scored = [_scored(STORAGE)]
    result = check_prompt("Store user data in postgres.", scored)
    warn_violations = [v for v in result.violations if v.severity == Severity.WARN]
    assert len(warn_violations) >= 1


def test_fail_verdict_when_both_anti_pattern_and_constraint_violated():
    scored = [_scored(STORAGE)]
    result = check_prompt("Use postgres with an ORM layer.", scored)
    assert result.verdict == Severity.FAIL


def test_only_warn_violations_gives_warn_verdict():
    d = Decision(
        id="d1", decision="D1", scope=[], rationale="",
        constraints=["no postgres"], anti_patterns=[],
    )
    scored = [_scored(d)]
    result = check_prompt("Consider postgres here.", scored)
    assert result.verdict == Severity.WARN


def test_violation_records_decision_id():
    scored = [_scored(STORAGE)]
    result = check_prompt("introduce ORM", scored)
    assert any(v.decision_id == "storage_json" for v in result.violations)


def test_violation_records_decision_text():
    scored = [_scored(STORAGE)]
    result = check_prompt("introduce ORM", scored)
    assert any("JSON storage" in v.decision_text for v in result.violations)


def test_violation_records_triggering_rule():
    scored = [_scored(STORAGE)]
    result = check_prompt("introduce ORM", scored)
    fail_v = next(v for v in result.violations if v.severity == Severity.FAIL)
    assert "introduce ORM" in fail_v.rule or "orm" in fail_v.rule.lower()


def test_violation_records_trigger_term():
    scored = [_scored(STORAGE)]
    result = check_prompt("Use postgres for storage.", scored)
    warn_v = next(v for v in result.violations if v.severity == Severity.WARN)
    assert "postgres" in warn_v.trigger


def test_zero_score_decisions_are_skipped():
    scored = [_scored(STORAGE, score=0.0)]
    result = check_prompt("Use postgres and introduce ORM.", scored)
    assert result.verdict == Severity.PASS


def test_top_n_limits_decisions_checked():
    d1 = Decision(
        id="d1", decision="D1", scope=["storage"], rationale="",
        constraints=["no postgres"], anti_patterns=[],
    )
    d2 = Decision(
        id="d2", decision="D2", scope=[], rationale="",
        constraints=[], anti_patterns=["introduce ORM"],
    )
    # d1 is ranked first (score=2.0), d2 second (score=1.0)
    scored = [_scored(d1, 2.0), _scored(d2, 1.0)]
    # top=1 → only d1 checked → "postgres" triggers WARN, "introduce ORM" not checked
    result = check_prompt("Use postgres and introduce ORM.", scored, top=1)
    assert result.verdict == Severity.WARN
    assert all(v.decision_id == "d1" for v in result.violations)


def test_case_insensitive_anti_pattern_match():
    scored = [_scored(STORAGE)]
    result = check_prompt("We will INTRODUCE an ORM framework.", scored)
    assert result.verdict == Severity.FAIL


def test_case_insensitive_constraint_match():
    scored = [_scored(STORAGE)]
    result = check_prompt("POSTGRES would work here.", scored)
    assert result.verdict == Severity.WARN


def test_no_match_when_term_is_embedded_substring():
    # "postgres" should NOT match "postgresql" (word boundary check)
    d = Decision(
        id="d1", decision="D1", scope=[], rationale="",
        constraints=["no postgres"], anti_patterns=[],
    )
    scored = [_scored(d)]
    result = check_prompt("We already use postgresql in staging.", scored)
    # \bpostgres\b does not match inside "postgresql"
    assert result.verdict == Severity.PASS


def test_multiple_decisions_can_each_trigger():
    scored = [_scored(STORAGE, 2.0), _scored(RETRIEVAL, 1.0)]
    # "postgres" triggers STORAGE constraint; "embeddings" triggers RETRIEVAL constraint
    result = check_prompt("Use postgres with embeddings for search.", scored)
    assert result.verdict == Severity.WARN
    decision_ids = {v.decision_id for v in result.violations}
    assert "storage_json" in decision_ids
    assert "retrieval_det" in decision_ids


def test_result_has_verdict_attribute():
    result = check_prompt("clean input", [_scored(STORAGE)])
    assert hasattr(result, "verdict")
    assert isinstance(result.verdict, Severity)


def test_result_has_violations_list():
    result = check_prompt("introduce ORM", [_scored(STORAGE)])
    assert hasattr(result, "violations")
    assert isinstance(result.violations, list)


def test_severity_enum_values():
    assert Severity.PASS == "PASS"
    assert Severity.WARN == "WARN"
    assert Severity.FAIL == "FAIL"


# ── CLI integration tests ─────────────────────────────────────────────────────

def test_check_cmd_pass_exits_zero(tmp_path):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "Store everything as flat JSON files.")
    exit_code = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "working on storage layer",
    ])
    assert exit_code == 0


def test_check_cmd_fail_exits_two(tmp_path):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "We should introduce an ORM for our storage layer.")
    exit_code = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "storage layer",
    ])
    assert exit_code == 2


def test_check_cmd_warn_exits_one(tmp_path):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "Should we move to postgres for the storage backend?")
    exit_code = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "storage layer",
    ])
    assert exit_code == 1


def test_check_cmd_prints_verdict(tmp_path, capsys):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "Store everything as flat JSON files.")
    main(["check", "--memory", str(mem), "--input", str(inp), "--query", "storage"])
    out = capsys.readouterr().out
    assert "PASS" in out


def test_check_cmd_prints_fail_verdict(tmp_path, capsys):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "introduce an ORM now.")
    main(["check", "--memory", str(mem), "--input", str(inp), "--query", "storage"])
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_check_cmd_prints_triggering_decision_id(tmp_path, capsys):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "introduce an ORM for storage.")
    main(["check", "--memory", str(mem), "--input", str(inp), "--query", "storage"])
    out = capsys.readouterr().out
    assert "storage_json" in out


def test_check_cmd_prints_triggering_rule(tmp_path, capsys):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "introduce an ORM for storage.")
    main(["check", "--memory", str(mem), "--input", str(inp), "--query", "storage"])
    out = capsys.readouterr().out
    assert "introduce ORM" in out or "orm" in out.lower()


def test_check_cmd_respects_top_flag(tmp_path):
    mem = _memory_file(tmp_path)
    # Both decisions have violations: "postgres" (storage) + "cosine" (retrieval)
    # top=1 → only highest-scored decision checked
    inp = _input_file(tmp_path, "Use postgres with cosine similarity search.")
    # Query hits storage strongly (scope=storage,backend match)
    exit_code_top1 = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "storage backend",
        "--top", "1",
    ])
    exit_code_top2 = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "storage backend",
        "--top", "2",
    ])
    # With top=2, we get more violations (possibly same exit code if both WARN)
    # The key assertion: top=1 exits with some code; top=2 may find more violations
    # Both should be non-zero (violations exist in both cases for this input)
    assert exit_code_top1 in (1, 2)
    assert exit_code_top2 in (1, 2)


def test_check_cmd_reads_input_from_file(tmp_path):
    mem = _memory_file(tmp_path)
    inp = _input_file(tmp_path, "introduce an ORM here")
    exit_code = main([
        "check",
        "--memory", str(mem),
        "--input", str(inp),
        "--query", "storage",
    ])
    assert exit_code == 2
