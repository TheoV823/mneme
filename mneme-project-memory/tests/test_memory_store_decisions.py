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


def test_legacy_anti_pattern_migration_does_not_dump_content_into_anti_patterns():
    """Migrating a legacy anti_pattern item must not push its entire content
    prose into the anti_patterns field. The enforcer tokenizes every entry
    in anti_patterns into forbidden terms, so dumping prose causes ordinary
    words ("between", "session", "module", "conversation") to be treated as
    forbidden — producing false-positive FAIL verdicts on innocent text.
    """
    store = MemoryStore(FIXTURES / "memory_legacy_only.json")
    memory = store.load()
    anti_dec = next(d for d in memory.decisions if d.id == "anti-001")
    assert "Do not use langchain" in anti_dec.anti_patterns
    content = "langchain adds weight and abstracts the API surface."
    assert content not in anti_dec.anti_patterns, (
        "Migration is dumping content prose into anti_patterns; "
        "every word in the content becomes a forbidden term."
    )
