"""Tests for the new Decision dataclass."""
from mneme.schemas import Decision


def test_decision_minimal_construction():
    d = Decision(id="mneme_001", decision="Use JSON storage only")
    assert d.id == "mneme_001"
    assert d.decision == "Use JSON storage only"
    assert d.rationale == ""
    assert d.scope == []
    assert d.constraints == []
    assert d.anti_patterns == []


def test_decision_full_construction():
    d = Decision(
        id="mneme_001",
        decision="Use JSON storage only",
        rationale="Avoid infra complexity and keep local-first",
        scope=["storage", "backend"],
        constraints=["no postgres", "no external db"],
        anti_patterns=["introduce ORM", "add migration layer"],
        created_at="2026-04-24T00:00:00Z",
        updated_at="2026-04-24T00:00:00Z",
    )
    assert d.scope == ["storage", "backend"]
    assert "no postgres" in d.constraints
    assert "introduce ORM" in d.anti_patterns


def test_decision_defaults_are_independent_lists():
    # Regression: mutable defaults must be per-instance, not shared.
    a = Decision(id="a", decision="x")
    b = Decision(id="b", decision="y")
    a.scope.append("storage")
    assert b.scope == []
