"""Tests for MemoryStore loading Decision records (native + legacy migration)."""
from pathlib import Path

from mneme.memory_store import MemoryStore

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_native_decisions():
    store = MemoryStore(FIXTURES / "memory_v2.json")
    memory = store.load()
    assert len(memory.decisions) == 1
    d = memory.decisions[0]
    assert d.id == "mneme_001"
    assert d.decision == "Use JSON storage only"
    assert d.scope == ["storage", "backend"]
    assert "no postgres" in d.constraints
    assert "introduce ORM" in d.anti_patterns


def test_legacy_rules_migrate_to_decisions():
    """Legacy rule + anti_pattern items must surface as Decisions."""
    store = MemoryStore(FIXTURES / "memory_legacy_only.json")
    memory = store.load()
    ids = {d.id for d in memory.decisions}
    assert "rule-001" in ids
    assert "anti-001" in ids

    rule_dec = next(d for d in memory.decisions if d.id == "rule-001")
    assert rule_dec.decision == "Extend current infrastructure before rebuilding"
    assert rule_dec.scope == ["general"]
    assert rule_dec.rationale == ""

    anti_dec = next(d for d in memory.decisions if d.id == "anti-001")
    # Legacy anti_pattern items land in the anti_patterns field.
    assert "Do not use langchain" in anti_dec.anti_patterns
    assert anti_dec.scope == ["general"]


def test_decisions_accessor():
    store = MemoryStore(FIXTURES / "memory_v2.json")
    store.load()
    assert len(store.decisions()) == 1
    assert store.decisions()[0].id == "mneme_001"
