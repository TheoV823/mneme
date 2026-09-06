"""M1.4 — Per-decision protection activation.

Covers the first complete product loop:

    Audit → Setup → candidate → validate → activate → canonical verify → Protected

Frozen invariants pinned here:

- eligibility comes exclusively from the canonical P1.2 assessment (G1);
- audit, setup, candidate discovery and validation never enable protection (G2);
- validation is deterministic engine behavior, never model judgment (G3);
- only the explicit activation path installs enforcement (G4);
- activated protection respects existing applicability semantics (G5);
- a decision cannot become Protected before canonical enforcement evidence
  is observable, and Current Protection never moves without it (G6);
- after successful activation a fresh audit independently observes the
  decision Protected and setup agrees (G7).
"""
import json
import os
import re
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from mneme.cli import main
from mneme.enforcer import generate_protection_report
from mneme.memory_store import MemoryStore
from mneme.protection import (
    ProtectionError,
    activate_protection,
    activation_precheck,
    find_candidates,
    protection_status,
    validate_proposal,
)
from mneme.schemas import Rule
from mneme.setup_state import derive_activation_state, read_activation

MEMORY_REL = Path(".mneme") / "project_memory.json"

BASE_TS = "2026-01-01T00:00:00Z"

DECISIONS = [
    {
        "id": "d_typed",
        "decision": "Store data in sqlite",
        "constraints": [],
        "anti_patterns": [],
        "rules": [{"type": "FORBID_LITERAL", "value": "sqlite"}],
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
    {
        "id": "d_ready",
        "decision": "No postgres in the service layer",
        "constraints": [],
        "anti_patterns": ["postgres"],
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
    {
        "id": "d_single_no",
        "decision": "Keep configuration in JSON",
        "constraints": ["no yaml"],
        "anti_patterns": [],
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
    {
        "id": "d_multi",
        "decision": "Keep services isolated",
        "constraints": [],
        "anti_patterns": ["share one database across services"],
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
    {
        "id": "d_guid",
        "decision": "Prefer small modules",
        "constraints": [],
        "anti_patterns": [],
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
    {
        "id": "d_superseded",
        "decision": "Old config rule",
        "constraints": [],
        "anti_patterns": ["xml"],
        "status": "superseded",
        "created_at": BASE_TS,
        "updated_at": BASE_TS,
    },
]


def _write_repo(
    tmp_path: Path,
    decisions: list[dict],
    activation: dict | None = None,
) -> tuple[Path, Path]:
    """Create a temporary repository with the fixture memory; return (root, memory)."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    memory = root / MEMORY_REL
    memory.parent.mkdir(parents=True)
    document = {
        "meta": {"name": "m14", "description": "M1.4 fixture"},
        "items": [],
        "examples": [],
        "decisions": decisions,
    }
    if activation is not None:
        document["activation"] = activation
    memory.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return root, memory


def _load_store(memory: Path) -> MemoryStore:
    store = MemoryStore(memory)
    store.load()
    return store


def _decision_by_id(store: MemoryStore, decision_id: str):
    return next(d for d in store.decisions() if d.id == decision_id)


def _audit_summary(memory: Path) -> dict:
    """Canonical audit metrics for the memory file, recomputed from disk."""
    store = _load_store(memory)
    report = generate_protection_report(store.decisions())
    return {
        "protected": report.protected,
        "mneme_ready": report.mneme_ready,
        "requires_modelling": report.requires_modelling,
        "guidance": report.guidance,
        "current_protection_pct": report.current_protection_pct,
    }


_SETUP_ACTIVATION = {
    "schema": "mneme.setup/v1",
    "state": "setup",
    "mneme_version": "0.6.0",
    "setup_started_at": BASE_TS,
    "setup_completed_at": BASE_TS,
    "activated_at": None,
    "audit_ref": "",
    "baseline": None,
    "integrations_detected": [],
    "integrations_configured": [],
    "enforcement": "not_enabled",
}


# ── G1: candidate eligibility is exclusively canonical ───────────────────────


def test_candidates_are_exactly_the_canonical_mneme_ready(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    store = _load_store(memory)
    discovered = find_candidates(store.decisions())

    ids = [c.decision_id for c in discovered.candidates]
    assert ids == ["d_ready", "d_single_no"]
    for candidate in discovered.candidates:
        assert candidate.proposal.type == "FORBID_LITERAL"
    by_id = {c.decision_id: c for c in discovered.candidates}
    assert by_id["d_ready"].guardrail == "FORBID_LITERAL: postgres"
    assert by_id["d_ready"].proposal.value == "postgres"
    assert by_id["d_single_no"].proposal.value == "yaml"

    report = discovered.report
    assert (report.protected, report.mneme_ready,
            report.requires_modelling, report.guidance) == (1, 2, 1, 1)


def test_already_protected_decision_is_not_a_candidate(tmp_path):
    _, memory = _write_repo(
        tmp_path, [d for d in DECISIONS if d["id"] == "d_typed"]
    )
    store = _load_store(memory)
    discovered = find_candidates(store.decisions())
    assert discovered.candidates == ()
    assert discovered.report.protected == 1
    assert discovered.report.mneme_ready == 0


def test_precheck_rejects_every_non_candidate(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    store = _load_store(memory)

    pre = activation_precheck(_decision_by_id(store, "d_multi"))
    assert pre.eligible is False and pre.tier == "requires_modelling"

    pre = activation_precheck(_decision_by_id(store, "d_guid"))
    assert pre.eligible is False and pre.tier == "guidance"

    pre = activation_precheck(_decision_by_id(store, "d_superseded"))
    assert pre.eligible is False
    assert "superseded" in pre.reason

    pre = activation_precheck(_decision_by_id(store, "d_typed"))
    assert pre.eligible is False and pre.tier == "protected"

    pre = activation_precheck(_decision_by_id(store, "d_ready"))
    assert pre.eligible is True and pre.proposal.value == "postgres"


# ── G2: nothing but the explicit activation path writes ──────────────────────


def test_discovery_and_validation_never_write(tmp_path, capsys):
    _, memory = _write_repo(tmp_path, DECISIONS)
    store = _load_store(memory)
    before = memory.read_text(encoding="utf-8")

    discovered = find_candidates(store.decisions())
    candidate = discovered.candidates[0]
    decision = _decision_by_id(store, candidate.decision_id)
    pre = activation_precheck(decision)
    assert validate_proposal(decision, pre.proposal).status == "valid"

    assert main(["protect", "list", "--memory", str(memory)]) == 0
    capsys.readouterr()
    assert main([
        "protect", "status", "d_ready", "--memory", str(memory),
    ]) == 0
    capsys.readouterr()
    assert main([
        "protect", "validate", "d_ready", "--memory", str(memory),
    ]) == 0
    capsys.readouterr()
    assert memory.read_text(encoding="utf-8") == before, (
        "a read-only protect operation wrote to the memory file"
    )


def test_audit_and_setup_never_activate(tmp_path, capsys):
    root, memory = _write_repo(tmp_path, DECISIONS)
    before = memory.read_text(encoding="utf-8")

    assert main([
        "audit", "--memory", str(memory), "--repo-root", str(root),
    ]) == 0
    capsys.readouterr()
    assert memory.read_text(encoding="utf-8") == before

    old = os.getcwd()
    os.chdir(root)
    try:
        assert main(["setup"]) == 0
        capsys.readouterr()
    finally:
        os.chdir(old)
    before_doc = json.loads(before)
    after_doc = json.loads(memory.read_text(encoding="utf-8"))
    before_rules = {
        e["id"]: e.get("rules", []) for e in before_doc["decisions"]
    }
    after_rules = {
        e["id"]: e.get("rules", []) for e in after_doc["decisions"]
    }
    assert after_rules == before_rules, "setup added or changed a rule"


# ── G3: deterministic validation ─────────────────────────────────────────────


def test_validation_success_all_four_checks(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    store = _load_store(memory)
    decision = _decision_by_id(store, "d_ready")
    pre = activation_precheck(decision)
    result = validate_proposal(decision, pre.proposal, memory_path=memory)

    assert result.status == "valid"
    assert [c.name for c in result.checks] == [
        "prohibited_detected",
        "permitted_allowed",
        "path_scope_respected",
        "unrelated_paths_unaffected",
    ]
    assert all(c.passed for c in result.checks)


def test_validation_unsupported_outside_activation_ready_shape(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    store = _load_store(memory)
    decision = _decision_by_id(store, "d_ready")

    scoped = Rule(
        type="FORBID_LITERAL", value="postgres",
        include_paths=("src/**",),
    )
    assert validate_proposal(
        decision, scoped, memory_path=memory
    ).status == "unsupported"

    bare = dc_replace(decision, memory_path="")
    pre = activation_precheck(bare)
    assert pre.eligible is True
    assert validate_proposal(
        bare, pre.proposal, memory_path=None
    ).status == "unsupported"


def test_validation_failure_refuses_activation(tmp_path, capsys, monkeypatch):
    """A failed deterministic validation writes nothing and protects nothing."""
    root, memory = _write_repo(tmp_path, DECISIONS)
    before = memory.read_text(encoding="utf-8")
    baseline = _audit_summary(memory)
    assert baseline["protected"] == 1 and baseline["mneme_ready"] == 2

    import mneme.protection as protection

    real_check = protection.check_prompt

    def blind_check(text, scored, top=3, input_path=None):
        result = real_check(text, scored, top=top, input_path=input_path)
        result.violations = [
            v for v in result.violations if v.kind != "typed_rule"
        ]
        return result

    monkeypatch.setattr(protection, "check_prompt", blind_check)
    try:
        outcome = activate_protection("d_ready", memory, repo_root=root)
        assert outcome.result == "validation_failed"
        assert outcome.rule_installed is False
        capsys.readouterr()
        code = main([
            "protect", "activate", "d_ready", "--memory", str(memory),
        ])
    finally:
        monkeypatch.undo()
    out = capsys.readouterr().out
    assert code == 1
    assert "VALIDATION FAILED" in out
    assert "Nothing was written" in out
    assert memory.read_text(encoding="utf-8") == before
    assert _audit_summary(memory) == baseline


# ── G4: explicit activation installs real enforcement ────────────────────────


def test_explicit_activation_installs_rule_and_verifies(tmp_path):
    root, memory = _write_repo(tmp_path, DECISIONS)
    before = json.loads(memory.read_text(encoding="utf-8"))

    outcome = activate_protection("d_ready", memory, repo_root=root)
    assert outcome.result == "verified"
    assert outcome.rule_installed is True
    assert outcome.verification_tier == "protected"

    raw = json.loads(memory.read_text(encoding="utf-8"))
    ready = next(e for e in raw["decisions"] if e["id"] == "d_ready")
    assert ready["rules"] == [{"type": "FORBID_LITERAL", "value": "postgres"}]
    others = [e for e in raw["decisions"] if e["id"] != "d_ready"]
    assert others == [e for e in before["decisions"] if e["id"] != "d_ready"]
    assert raw["meta"] == before["meta"]


def test_activation_via_cli(tmp_path, capsys):
    root, memory = _write_repo(tmp_path, DECISIONS)

    capsys.readouterr()
    code = main([
        "protect", "activate", "d_single_no", "--memory", str(memory),
        "--repo-root", str(root),
    ])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "activated and verified" in out
    raw = json.loads(memory.read_text(encoding="utf-8"))
    entry = next(e for e in raw["decisions"] if e["id"] == "d_single_no")
    assert entry["rules"] == [{"type": "FORBID_LITERAL", "value": "yaml"}]


def test_activation_is_idempotent_and_never_duplicates(tmp_path):
    root, memory = _write_repo(tmp_path, DECISIONS)

    first = activate_protection("d_ready", memory, repo_root=root)
    assert first.result == "verified" and first.rule_installed is True

    second = activate_protection("d_ready", memory, repo_root=root)
    assert second.result == "already_protected"
    assert second.rule_installed is False

    assert activate_protection("d_ready", memory).result == "already_protected"

    raw = json.loads(memory.read_text(encoding="utf-8"))
    ready = next(e for e in raw["decisions"] if e["id"] == "d_ready")
    assert ready["rules"] == [{"type": "FORBID_LITERAL", "value": "postgres"}]


def test_ineligible_decisions_cannot_be_activated(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    before = memory.read_text(encoding="utf-8")

    assert activate_protection("d_superseded", memory).result == "not_eligible"
    assert activate_protection("d_multi", memory).result == "not_eligible"
    assert activate_protection("d_guid", memory).result == "not_eligible"
    outcome = activate_protection("d_typed", memory)
    assert outcome.result == "already_protected"
    assert outcome.rule_installed is False
    assert memory.read_text(encoding="utf-8") == before


def test_activate_unknown_decision_is_usage_error(tmp_path, capsys):
    _, memory = _write_repo(tmp_path, DECISIONS)
    capsys.readouterr()
    code = main(["protect", "activate", "nope", "--memory", str(memory)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("ERROR")
    assert captured.out == ""


def test_activate_refuses_unsupported_activation_record(tmp_path, capsys):
    _, memory = _write_repo(
        tmp_path, DECISIONS,
        activation={"schema": "someone.else/v9", "state": "setup"},
    )
    before = memory.read_text(encoding="utf-8")
    capsys.readouterr()
    code = main(["protect", "activate", "d_ready", "--memory", str(memory)])
    captured = capsys.readouterr()
    assert code == 2
    assert "refusing" in captured.err
    assert memory.read_text(encoding="utf-8") == before


# ── G5: applicability semantics of the activated rule ────────────────────────


def test_activated_protection_enforces_and_exempts_canonical_sources(
    tmp_path, capsys,
):
    root, memory = _write_repo(tmp_path, DECISIONS)
    assert activate_protection("d_ready", memory).result == "verified"

    violating = root / "violating.py"
    violating.write_text("use postgres here\n", encoding="utf-8")
    permitted = root / "clean.py"
    permitted.write_text("use an embedded key-value store here\n", encoding="utf-8")

    capsys.readouterr()
    code = main([
        "check", "--memory", str(memory), "--input", str(violating),
        "--query", "service layer", "--adr-dir", "docs/adr-absent",
    ])
    out = capsys.readouterr().out
    assert code == 2
    assert 'FORBID_LITERAL "postgres"' in out

    capsys.readouterr()
    code = main([
        "check", "--memory", str(memory), "--input", str(permitted),
        "--query", "service layer", "--adr-dir", "docs/adr-absent",
    ])
    assert code == 0

    capsys.readouterr()
    # The memory file carrying the rule is a canonical policy source: the
    # activated typed rule must be exempt there (ADR-019 #6 / ADR-020 #8),
    # even though legacy anti-pattern prose still applies to any text.
    code = main([
        "check", "--memory", str(memory), "--input", str(memory),
        "--query", "service layer", "--adr-dir", "docs/adr-absent",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    typed = [v for v in payload["violations"] if v["kind"] == "typed_rule"]
    assert typed == [], typed
    exempt_traces = [
        a for a in payload["applicability"]
        if a["rule_type"] == "FORBID_LITERAL"
        and a["decision_id"] == "d_ready"
        and a["outcome"] == "EXCLUDED"
    ]
    assert exempt_traces and exempt_traces[0]["selector"] == (
        "<canonical-policy-source>"
    ), payload["applicability"]


# ── G6: score moves only when canonical evidence exists ──────────────────────


def test_activation_without_evidence_does_not_move_score(
    tmp_path, monkeypatch,
):
    root, memory = _write_repo(tmp_path, DECISIONS)
    baseline = _audit_summary(memory)
    assert baseline["protected"] == 1 and baseline["mneme_ready"] == 2
    assert baseline["current_protection_pct"] == 25.0

    import mneme.protection as protection

    monkeypatch.setattr(protection, "_install_rule", lambda *a, **k: False)
    try:
        outcome = activate_protection("d_ready", memory, repo_root=root)
    finally:
        monkeypatch.undo()
    assert outcome.result == "verification_failed"
    assert outcome.rule_installed is False
    assert outcome.verification_tier == "mneme_ready"

    after = _audit_summary(memory)
    assert after == baseline, (
        "activation without verifiable enforcement evidence "
        "must not increase Current Protection"
    )


def test_validate_alone_does_not_change_classification(tmp_path, capsys):
    _, memory = _write_repo(tmp_path, DECISIONS)
    baseline = _audit_summary(memory)
    before = memory.read_text(encoding="utf-8")

    assert main(["protect", "validate", "d_ready", "--memory", str(memory)]) == 0
    capsys.readouterr()

    assert _audit_summary(memory) == baseline
    assert memory.read_text(encoding="utf-8") == before


def test_cli_activate_reports_verification_failure(tmp_path, capsys, monkeypatch):
    root, memory = _write_repo(tmp_path, DECISIONS)
    import mneme.protection as protection

    monkeypatch.setattr(protection, "_install_rule", lambda *a, **k: False)
    try:
        capsys.readouterr()
        code = main([
            "protect", "activate", "d_ready", "--memory", str(memory),
            "--repo-root", str(root),
        ])
    finally:
        monkeypatch.undo()
    captured = capsys.readouterr()
    assert code == 1
    assert "remains NOT Protected" in captured.out
    assert "activated and verified" not in captured.out


# ── G7: re-audit parity after activation ─────────────────────────────────────


def test_fresh_audit_and_setup_observe_activated_protection(tmp_path, capsys):
    root, memory = _write_repo(tmp_path, DECISIONS)
    baseline = _audit_summary(memory)
    assert baseline["protected"] == 1 and baseline["mneme_ready"] == 2
    assert baseline["current_protection_pct"] == 25.0

    assert activate_protection("d_ready", memory, repo_root=root).result == (
        "verified"
    )

    after = _audit_summary(memory)
    assert after["protected"] == 2 and after["mneme_ready"] == 1
    assert after["current_protection_pct"] == 50.0
    assert after["requires_modelling"] == baseline["requires_modelling"]
    assert after["guidance"] == baseline["guidance"]

    old = os.getcwd()
    os.chdir(root)
    try:
        capsys.readouterr()
        assert main(["setup"]) == 0
        setup_out = capsys.readouterr().out
    finally:
        os.chdir(old)
    setup_counts = {}
    for key in ("Protected", "Mneme-ready", "Requires modelling", "Guidance"):
        match = re.search(rf"^\s*{re.escape(key)}: (\d+)$", setup_out, re.M)
        assert match, f"missing {key} in setup summary: {setup_out}"
        setup_counts[key] = int(match.group(1))
    assert setup_counts == {
        "Protected": 2,
        "Mneme-ready": 1,
        "Requires modelling": 1,
        "Guidance": 1,
    }


def test_activation_performs_the_reserved_setup_to_active_transition(tmp_path):
    _, memory = _write_repo(
        tmp_path, DECISIONS, activation=_SETUP_ACTIVATION
    )
    assert activate_protection("d_ready", memory).result == "verified"

    record = json.loads(memory.read_text(encoding="utf-8"))["activation"]
    assert record["state"] == "active"
    assert record["activated_at"]
    assert record["setup_completed_at"] == BASE_TS
    assert record["enforcement"] == "not_enabled"


def test_setup_still_refuses_active_projects_after_activation(tmp_path, capsys):
    """Frozen M1.3 behavior: setup never downgrades an active project."""
    root, memory = _write_repo(
        tmp_path, DECISIONS, activation=_SETUP_ACTIVATION
    )
    assert activate_protection("d_ready", memory).result == "verified"
    before = memory.read_text(encoding="utf-8")

    old = os.getcwd()
    os.chdir(root)
    try:
        capsys.readouterr()
        code = main(["setup"])
        out = capsys.readouterr().out
    finally:
        os.chdir(old)
    assert code == 0
    assert "active state" in out
    assert memory.read_text(encoding="utf-8") == before


def test_activation_persists_active_record_for_pre_m13_memory(
    tmp_path, capsys,
):
    """Frozen M1.3 invariant: verified protection implies state ``active``.

    A pre-M1.3 memory file with no activation record is de-facto ``setup``
    (``derive_activation_state``). Explicit activation of the first
    protection must leave a valid ``active`` record behind — never the
    invalid "Protected decision + setup project" combination — while
    reusing the existing M1.3 schema, transition table and persistence.
    """
    root, memory = _write_repo(tmp_path, DECISIONS)

    # 1 — before activation the project derives as setup.
    assert derive_activation_state(memory) == "setup"
    assert read_activation(memory) is None

    # 2 — explicit activation succeeds and canonical verification passes.
    outcome = activate_protection("d_single_no", memory, repo_root=root)
    assert outcome.result == "verified"
    assert outcome.verification_tier == "protected"

    # 3+4+5 — the project is now active with a valid, populated record.
    assert derive_activation_state(memory) == "active"
    record = read_activation(memory)
    assert record is not None
    assert record.state == "active"
    assert record.activated_at
    assert record.to_dict()["schema"] == "mneme.setup/v1"

    # 6 — setup cannot subsequently downgrade the project.
    before = memory.read_text(encoding="utf-8")
    old = os.getcwd()
    os.chdir(root)
    try:
        capsys.readouterr()
        code = main(["setup"])
        out = capsys.readouterr().out
    finally:
        os.chdir(old)
    assert code == 0
    assert "active state" in out
    assert memory.read_text(encoding="utf-8") == before
    assert read_activation(memory).state == "active"


# ── Status surface ───────────────────────────────────────────────────────────


def test_status_reflects_each_lifecycle_stage(tmp_path, capsys):
    _, memory = _write_repo(tmp_path, DECISIONS)

    status = protection_status("d_ready", memory)
    assert status.tier == "mneme_ready" and status.rule_installed is False
    assert status.proposal is not None and status.proposal.value == "postgres"

    capsys.readouterr()
    assert main(["protect", "status", "d_ready", "--memory", str(memory)]) == 0
    out = capsys.readouterr().out
    assert "mneme_ready" in out and "rule installed:   no" in out

    assert activate_protection("d_ready", memory).result == "verified"
    status = protection_status("d_ready", memory)
    assert status.tier == "protected" and status.rule_installed is True
    assert status.proposal is None

    capsys.readouterr()
    assert main(["protect", "status", "d_ready", "--memory", str(memory)]) == 0
    out = capsys.readouterr().out
    assert "protected" in out and "rule installed:   yes" in out

    capsys.readouterr()
    code = main(["protect", "status", "nope", "--memory", str(memory)])
    captured = capsys.readouterr()
    assert code == 2 and captured.err.startswith("ERROR")


def test_errors_raise_before_any_write(tmp_path):
    _, memory = _write_repo(tmp_path, DECISIONS)
    before = memory.read_text(encoding="utf-8")
    with pytest.raises(ProtectionError):
        activate_protection("ghost", memory)
    with pytest.raises(ProtectionError):
        protection_status("ghost", memory)
    assert memory.read_text(encoding="utf-8") == before


# ── CLI error paths: clean exit 2, never a traceback ─────────────────────────


_PROTECT_SUBCOMMANDS = [
    ("list",),
    ("status", "d_ready"),
    ("validate", "d_ready"),
    ("activate", "d_ready"),
]


def test_protect_cli_missing_memory_is_clean_usage_error(
    tmp_path, capsys,
):
    missing = tmp_path / "absent" / "project_memory.json"
    for subcommand in _PROTECT_SUBCOMMANDS:
        capsys.readouterr()
        code = main([
            "protect", *subcommand, "--memory", str(missing),
        ])
        captured = capsys.readouterr()
        assert code == 2, (subcommand, captured.out, captured.err)
        assert captured.out == ""
        assert captured.err.startswith("ERROR: memory file"), captured.err
        assert "Traceback" not in captured.err
        assert not missing.exists(), "a failed protect command wrote memory"


def test_protect_cli_invalid_memory_is_clean_usage_error(
    tmp_path, capsys,
):
    malformed = tmp_path / "broken.json"
    malformed.write_text("{ not valid json ]", encoding="utf-8")
    invalid_schema = tmp_path / "badrule.json"
    invalid_schema.write_text(json.dumps({
        "meta": {"name": "x", "description": "x"},
        "items": [],
        "examples": [],
        "decisions": [{
            "id": "d_ready",
            "decision": "No postgres in the service layer",
            "anti_patterns": ["postgres"],
            "rules": [{"type": "NOT_A_TYPE", "value": "postgres"}],
        }],
    }, indent=2) + "\n", encoding="utf-8")

    for memory in (malformed, invalid_schema):
        before = memory.read_text(encoding="utf-8")
        for subcommand in _PROTECT_SUBCOMMANDS:
            capsys.readouterr()
            code = main([
                "protect", *subcommand, "--memory", str(memory),
            ])
            captured = capsys.readouterr()
            assert code == 2, (subcommand, captured.out, captured.err)
            assert captured.out == ""
            assert captured.err.startswith("ERROR:"), captured.err
            assert "Traceback" not in captured.err
            assert memory.read_text(encoding="utf-8") == before


# ── Full product loop (realistic end-to-end fixture) ─────────────────────────


def test_full_loop_audit_validate_activate_verify_audit(tmp_path, capsys):
    """ADR/decision → audit (Mneme-ready) → validate → activate → evidence →
    fresh canonical audit → Protected; setup parity throughout; score moves
    only with canonical evidence."""
    root, memory = _write_repo(tmp_path, DECISIONS)

    # 1+2 — the candidate starts Mneme-ready / Protectable, unprotected.
    initial = _audit_summary(memory)
    assert initial["mneme_ready"] == 2 and initial["protected"] == 1
    assert initial["current_protection_pct"] == 25.0

    # 2 — validation alone does not make it Protected.
    capsys.readouterr()
    assert main([
        "protect", "validate", "d_ready", "--memory", str(memory),
        "--repo-root", str(root),
    ]) == 0
    assert "Result: VALID" in capsys.readouterr().out
    assert _audit_summary(memory) == initial

    # 3 — explicit activation.
    capsys.readouterr()
    assert main([
        "protect", "activate", "d_ready", "--memory", str(memory),
        "--repo-root", str(root),
    ]) == 0
    assert "activated and verified" in capsys.readouterr().out

    # 4 — real mechanical enforcement evidence exists and works both ways.
    raw = json.loads(memory.read_text(encoding="utf-8"))
    entry = next(e for e in raw["decisions"] if e["id"] == "d_ready")
    assert entry["rules"] == [{"type": "FORBID_LITERAL", "value": "postgres"}]

    violating = root / "src"
    violating.mkdir()
    violating_file = violating / "service.py"
    violating_file.write_text("import postgres\n", encoding="utf-8")
    permitted_file = violating / "service_ok.py"
    permitted_file.write_text("import sqlite3\n", encoding="utf-8")

    capsys.readouterr()
    assert main([
        "check", "--memory", str(memory), "--input", str(violating_file),
        "--query", "service layer", "--adr-dir", "docs/adr-absent",
    ]) == 2
    assert "FORBID_LITERAL \"postgres\"" in capsys.readouterr().out
    capsys.readouterr()
    assert main([
        "check", "--memory", str(memory), "--input", str(permitted_file),
        "--query", "service layer", "--adr-dir", "docs/adr-absent",
    ]) == 0

    # 5+6 — a fresh canonical audit independently observes Protected, and
    # Current Protection moved only because canonical evidence changed.
    final = _audit_summary(memory)
    assert final["protected"] == 2 and final["mneme_ready"] == 1
    assert final["current_protection_pct"] == 50.0

    # 7 — setup/readiness sees the same classification.
    old = os.getcwd()
    os.chdir(root)
    try:
        capsys.readouterr()
        assert main(["setup"]) == 0
        setup_out = capsys.readouterr().out
    finally:
        os.chdir(old)
    counts = {}
    for key in ("Protected", "Mneme-ready", "Requires modelling", "Guidance"):
        match = re.search(rf"^\s*{re.escape(key)}: (\d+)$", setup_out, re.M)
        counts[key] = int(match.group(1))
    assert counts == {
        "Protected": 2,
        "Mneme-ready": 1,
        "Requires modelling": 1,
        "Guidance": 1,
    }
