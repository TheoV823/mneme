"""setup_state — activation record, transitions, persistence, readiness."""
import json
from pathlib import Path

import pytest

from mneme.readiness import assess_readiness, readiness_counts
from mneme.setup_state import (
    ACTIVATION_SCHEMA,
    STATE_ACTIVE,
    STATE_NOT_INSTALLED,
    STATE_SETUP,
    ActivationRecord,
    ActivationStateError,
    derive_activation_state,
    read_activation,
    scaffold_project_memory,
    write_activation,
)
from mneme.schemas import Decision, Rule


# ── Scaffold ──────────────────────────────────────────────────────────────────

def test_scaffold_shape():
    doc = scaffold_project_memory(created_by="mneme setup")
    assert doc["meta"]["created_by"] == "mneme setup"
    assert doc["meta"]["name"] == ""
    assert doc["items"] == []
    assert doc["examples"] == []
    assert doc["decisions"] == []
    assert "activation" not in doc


# ── ActivationRecord ─────────────────────────────────────────────────────────

def test_record_roundtrip():
    record = ActivationRecord(
        state=STATE_SETUP,
        mneme_version="0.6.0",
        setup_started_at="2026-09-05T00:00:00Z",
        setup_completed_at="2026-09-05T00:00:01Z",
        audit_ref="ref-123",
        integrations_detected=["claude_code"],
        integrations_configured=[],
        enforcement="not_enabled",
    )
    raw = record.to_dict()
    assert raw["schema"] == ACTIVATION_SCHEMA
    assert raw["enforcement"] == "not_enabled"
    parsed = ActivationRecord.from_dict(raw)
    assert parsed == record


def test_record_from_dict_rejects_unknown_state():
    with pytest.raises(ActivationStateError):
        ActivationRecord.from_dict({"state": "enforcing"})


def test_record_from_dict_rejects_non_object():
    with pytest.raises(ActivationStateError):
        ActivationRecord.from_dict("setup")


def test_record_from_dict_rejects_bad_baseline():
    with pytest.raises(ActivationStateError):
        ActivationRecord.from_dict({"state": "setup", "baseline": "x"})


def test_record_from_dict_rejects_bad_integrations():
    with pytest.raises(ActivationStateError):
        ActivationRecord.from_dict({"state": "setup", "integrations_detected": [1]})


# ── Transitions ───────────────────────────────────────────────────────────────

def test_transition_not_installed_to_setup_allowed():
    ActivationRecord(state=STATE_NOT_INSTALLED).require_transition(STATE_SETUP)


def test_transition_not_installed_to_active_rejected():
    # Activation to active without setup would be an implicit bypass of the
    # frozen state model; it must fail.
    with pytest.raises(ActivationStateError):
        ActivationRecord(state=STATE_NOT_INSTALLED).require_transition(STATE_ACTIVE)


def test_transition_setup_to_active_allowed_only_explicitly():
    ActivationRecord(state=STATE_SETUP).require_transition(STATE_ACTIVE)


def test_transition_active_to_setup_rejected():
    # Setup must never downgrade an active project.
    with pytest.raises(ActivationStateError):
        ActivationRecord(state=STATE_ACTIVE).require_transition(STATE_SETUP)


# ── Persistence ───────────────────────────────────────────────────────────────

def _write_memory(path: Path, **extra) -> None:
    doc = scaffold_project_memory()
    doc["decisions"].append(
        {
            "id": "d1",
            "decision": "Use JSON",
            "constraints": ["no yaml"],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    doc.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def test_read_activation_missing_section_returns_none(tmp_path):
    memory = tmp_path / "project_memory.json"
    _write_memory(memory)
    assert read_activation(memory) is None


def test_derive_state_lifecycle(tmp_path):
    memory = tmp_path / "project_memory.json"
    # No file at all → not_installed.
    assert derive_activation_state(memory) == STATE_NOT_INSTALLED
    _write_memory(memory)
    # File without activation record (pre-M1.3 project) → setup.
    assert derive_activation_state(memory) == STATE_SETUP
    write_activation(
        memory,
        ActivationRecord(state=STATE_SETUP, setup_completed_at="t"),
    )
    assert derive_activation_state(memory) == STATE_SETUP
    write_activation(memory, ActivationRecord(state=STATE_ACTIVE))
    assert derive_activation_state(memory) == STATE_ACTIVE


def test_write_activation_preserves_all_other_content(tmp_path):
    memory = tmp_path / "project_memory.json"
    _write_memory(memory, custom_section={"keep": [1, 2]})
    before = json.loads(memory.read_text(encoding="utf-8"))

    write_activation(memory, ActivationRecord(state=STATE_SETUP))

    after = json.loads(memory.read_text(encoding="utf-8"))
    after_without_activation = {k: v for k, v in after.items() if k != "activation"}
    assert after_without_activation == before
    assert after["activation"]["state"] == "setup"
    assert after["activation"]["enforcement"] == "not_enabled"
    # decisions content untouched
    assert after["decisions"] == before["decisions"]
    assert after["meta"] == before["meta"]
    assert after["custom_section"] == {"keep": [1, 2]}


def test_write_activation_requires_existing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_activation(tmp_path / "missing.json", ActivationRecord(state=STATE_SETUP))


def test_read_activation_invalid_record_raises(tmp_path):
    memory = tmp_path / "project_memory.json"
    _write_memory(memory, activation={"state": "bogus"})
    with pytest.raises(ActivationStateError):
        read_activation(memory)


# ── Readiness (G4 semantics — delegated to frozen P1.2) ─────────────────────

def test_readiness_protected_requires_typed_rule():
    # FORBID_LITERAL typed rule = verified mechanical protection evidence.
    d = Decision(id="a", decision="x", rules=[Rule(type="FORBID_LITERAL", value="postgres")])
    assert assess_readiness(d) == "protected"


def test_readiness_single_term_anti_pattern_is_not_protected():
    # Single-term anti-patterns are "enforceable" by the core enforcer, but
    # without a typed rule there is no existing protection evidence: the
    # decision is Mneme-ready, NOT Protected. Installing Mneme must never
    # cross this line (G4).
    d = Decision(id="b", decision="x", anti_patterns=["postgres"])
    assert assess_readiness(d) == "mneme_ready"


def test_readiness_multi_term_anti_pattern_requires_modelling():
    d = Decision(id="c", decision="x", anti_patterns=["no shared database between services"])
    assert assess_readiness(d) == "requires_modelling"


def test_readiness_single_term_no_x_constraint_is_mneme_ready():
    # Canonical P1.2: a single-term "no X" constraint carries a concrete
    # safe guardrail (FORBID_LITERAL: <term>), so it is Mneme-ready.
    d = Decision(id="d", decision="x", constraints=["no postgres"])
    assert assess_readiness(d) == "mneme_ready"


def test_readiness_multi_term_no_x_constraint_requires_modelling():
    d = Decision(id="d2", decision="x", constraints=["no shared database between services"])
    assert assess_readiness(d) == "requires_modelling"


def test_readiness_prose_only_is_guidance():
    d = Decision(id="e", decision="prefer small modules", rationale="style")
    assert assess_readiness(d) == "guidance"


def test_readiness_is_never_upgraded_without_verified_ci_evidence(tmp_path):
    # A CI file merely MENTIONING the token is candidate evidence at best:
    # candidate evidence annotates but never upgrades a tier (frozen P1.2).
    root = tmp_path / "repo"
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "jobs:\n  scan:\n    steps:\n      - run: grep postgres src/\n",
        encoding="utf-8",
    )
    d = Decision(id="f", decision="x", anti_patterns=["postgres"])
    assert assess_readiness(d, repo_root=str(root)) == "mneme_ready"


def test_readiness_counts_match_audit_report_for_active_decisions():
    # The setup counts are exactly the canonical aggregate report values.
    from mneme.enforcer import generate_protection_report

    decisions = [
        Decision(id="a", decision="x", rules=[Rule(type="FORBID_LITERAL", value="sqlite")]),
        Decision(id="b", decision="x", anti_patterns=["orm"]),
        Decision(id="c", decision="x", anti_patterns=["share one database across services"]),
        Decision(id="d", decision="prefer clarity"),
        # Superseded/deprecated decisions are provenance-only in P1.2.
        Decision(id="old-1", decision="superseded rule", anti_patterns=["yaml"], status="superseded"),
        Decision(id="old-2", decision="deprecated rule", rules=[Rule(type="FORBID_LITERAL", value="yaml")], status="deprecated"),
    ]
    counts = readiness_counts(decisions)
    report = generate_protection_report(decisions)
    assert counts == {
        "protected": report.protected,
        "mneme_ready": report.mneme_ready,
        "requires_modelling": report.requires_modelling,
        "guidance": report.guidance,
    }
    # Inactive decisions never enter the counts (G4: setup cannot inflate
    # protection via status games either way — both views agree).
    assert counts == {
        "protected": 1,
        "mneme_ready": 1,
        "requires_modelling": 1,
        "guidance": 1,
    }
