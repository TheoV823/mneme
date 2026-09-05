"""CLI — `mneme setup` (M1.3a setup flow; M1.3b pairing; G1/G2/G3/G4/G5)."""
import json
import subprocess
from pathlib import Path

import pytest

from mneme.audit_pairing import PairingError
from mneme.cli import main


MEMORY_REL = Path(".mneme") / "project_memory.json"

RESOLVE_RESPONSE = {
    "reference": "ref-abc",
    "audit_id": "00000000-0000-0000-0000-000000000001",
    "project_id": "00000000-0000-0000-0000-000000000002",
    "project_name": "contract-fixture",
    "repository": "example/contract-fixture",
    "repository_url": "https://github.com/example/contract-fixture",
    "commit_sha": "abc123def456",
    "mneme_version": "0.6.0",
    "schema_version": 1,
    "audit_schema": "mneme.audit/v1",
    "summary": {"protected": 2, "mneme_ready": 3},
}


class FakePairing:
    """In-memory stand-in for the Architecture Audit pairing client."""

    def __init__(self):
        self.resolve_calls: list[str] = []
        self.resolve_error: str | None = None
        self.resolve_response: dict = dict(RESOLVE_RESPONSE)
        self.complete_error: str | None = None
        self.complete_calls: list[dict] = []

    def resolve(self, reference: str) -> dict:
        self.resolve_calls.append(reference)
        if self.resolve_error:
            raise PairingError(self.resolve_error, status=410)
        return dict(self.resolve_response)

    def complete(self, reference: str, repository, mneme_version: str) -> dict:
        self.complete_calls.append({
            "reference": reference,
            "repository": repository,
            "mneme_version": mneme_version,
        })
        if self.complete_error:
            raise PairingError(self.complete_error, status=503)
        return {"activation_state": "setup", "already_redeemed": False}


@pytest.fixture(autouse=True)
def fake_pairing(monkeypatch):
    """No test talks to the network: the CLI pairing client is always faked."""
    fake = FakePairing()
    monkeypatch.setattr("mneme.setup.default_pairing", lambda: fake)
    return fake


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal repository root. find_project_root only needs a
    .git marker, so tests stay hermetic (no git subprocess required)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


def _make_worktree_style_repo(tmp_path: Path) -> Path:
    """Repository root whose .git is a file, as in linked worktrees."""
    (tmp_path / ".git").write_text("gitdir: ../elsewhere/.git/worktrees/x\n", encoding="utf-8")
    return tmp_path


def _read_memory(tmp_path: Path) -> dict:
    return json.loads((tmp_path / MEMORY_REL).read_text(encoding="utf-8"))


def _write_memory_with_decisions(tmp_path: Path) -> dict:
    doc = {
        "meta": {
            "name": "payments-api",
            "description": "existing project",
            "created_by": "mneme init",
            "created": "2026-01-01T00:00:00Z",
        },
        "items": [
            {
                "id": "legacy-1",
                "type": "rule",
                "title": "Use JSON config",
                "content": "configuration must be JSON",
                "tags": [],
                "priority": "medium",
            }
        ],
        "examples": [],
        "decisions": [
            {
                "id": "d_typed",
                "decision": "Store data in sqlite",
                "rationale": "embedded",
                "scope": ["storage"],
                "constraints": [],
                "anti_patterns": [],
                "rules": [{"type": "FORBID_LITERAL", "value": "postgres"}],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "d_single_ap",
                "decision": "Avoid ORM indirection",
                "rationale": "",
                "scope": ["storage"],
                "constraints": [],
                "anti_patterns": ["orm"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "d_multi_ap",
                "decision": "Keep services isolated",
                "rationale": "",
                "scope": [],
                "constraints": [],
                "anti_patterns": ["share one database across services"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "id": "d_guidance",
                "decision": "Prefer small modules",
                "rationale": "readability",
                "scope": [],
                "constraints": [],
                "anti_patterns": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ],
    }
    (tmp_path / MEMORY_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / MEMORY_REL).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


# ── G1: safe setup on a fresh repository ─────────────────────────────────────

def test_setup_fresh_repo_initializes_in_setup_mode(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = _read_memory(root)
    record = data["activation"]
    assert record["state"] == "setup"
    assert record["enforcement"] == "not_enabled"
    assert record["schema"] == "mneme.setup/v1"
    assert record["activated_at"] is None
    assert record["integrations_configured"] == []
    assert record["audit_ref"] == ""
    assert data["meta"]["created_by"] == "mneme setup"
    assert "Mneme is installed in setup mode." in captured.out
    assert "Not enabled" in captured.out


def test_setup_creates_nothing_but_mneme_state(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    pre_existing = root / "src"
    pre_existing.mkdir()
    (pre_existing / "app.py").write_text("print('hi')\n", encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    assert exit_code == 0

    created = {p.relative_to(root).as_posix() for p in root.rglob("*")}
    # Only the .mneme memory file may appear; no hook configs, no integrations.
    assert created == {".git", "src", "src/app.py", ".mneme", MEMORY_REL.as_posix()}


def test_setup_does_not_touch_existing_agent_configuration(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    claude_dir = root / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.json"
    original = '{"hooks": {}}'
    settings.write_text(original, encoding="utf-8")

    monkeypatch.chdir(root)
    assert main(["setup"]) == 0

    # Detection must not mutate the detected environment, and setup must not
    # install any enforcement hook configuration (G1 + G5 invariant).
    assert settings.read_text(encoding="utf-8") == original


def test_setup_reports_project_and_memory(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    out = capsys.readouterr().out
    assert root.name in out
    assert "Project memory" in out
    assert "Created" in out


def test_setup_requires_git_repository(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # no .git anywhere above
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ERROR" in captured.err
    assert not (tmp_path / MEMORY_REL).exists()
    assert list(tmp_path.iterdir()) == []


def test_setup_from_subdirectory_targets_repo_root(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    subdir = root / "services" / "billing"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    assert main(["setup"]) == 0
    data = _read_memory(root)
    assert data["activation"]["state"] == "setup"
    assert data["meta"]["name"] == root.name
    assert not (subdir / MEMORY_REL).exists()


def test_setup_accepts_worktree_style_git_file(tmp_path, monkeypatch):
    root = _make_worktree_style_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    assert _read_memory(root)["activation"]["state"] == "setup"


def test_setup_scaffold_loads_through_memory_store(tmp_path, monkeypatch):
    from mneme.memory_store import MemoryStore

    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    store = MemoryStore(root / MEMORY_REL)
    store.load()
    assert store.decisions() == []


# ── G2: idempotency and existing projects ────────────────────────────────────

def test_setup_rerun_is_byte_identical(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    assert main(["setup"]) == 0
    first = (root / MEMORY_REL).read_text(encoding="utf-8")

    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert (root / MEMORY_REL).read_text(encoding="utf-8") == first
    assert "already in setup mode" in captured.out


def test_setup_existing_project_preserves_all_content(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    original = _write_memory_with_decisions(root)
    memory_file = root / MEMORY_REL

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    after = json.loads(memory_file.read_text(encoding="utf-8"))
    # Every pre-existing top-level section survives byte-for-byte in content.
    for key, value in original.items():
        assert after[key] == value, key
    # Only the activation section is added.
    assert set(after) - set(original) == {"activation"}
    assert after["activation"]["state"] == "setup"
    assert "already in setup mode" not in captured.out


def test_setup_rerun_on_existing_project_preserves_first_completion(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    assert main(["setup"]) == 0
    first_record = _read_memory(root)["activation"]

    exit_code = main(["setup"])
    assert exit_code == 0
    second_record = _read_memory(root)["activation"]

    assert second_record["setup_completed_at"] == first_record["setup_completed_at"]
    assert second_record["setup_started_at"] == first_record["setup_started_at"]


def test_setup_rerun_with_new_audit_ref_updates_ref_only(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    assert main(["setup"]) == 0
    first = _read_memory(root)["activation"]

    exit_code = main(["setup", "--audit-ref", "ref-999"])
    captured = capsys.readouterr()
    assert exit_code == 0

    second = _read_memory(root)["activation"]
    assert second["audit_ref"] == "ref-999"
    assert second["setup_completed_at"] == first["setup_completed_at"]
    # A fresh reference resolves to a connected baseline.
    assert second["baseline"]["audit_id"] == RESOLVE_RESPONSE["audit_id"]
    assert "Connected: contract-fixture" in captured.out


def test_setup_on_corrupt_memory_fails_without_mutation(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    memory_file = root / MEMORY_REL
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    original = "{not json"
    memory_file.write_text(original, encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ERROR" in captured.err
    assert memory_file.read_text(encoding="utf-8") == original


def test_setup_on_invalid_activation_record_fails_without_mutation(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    _write_memory_with_decisions(root)
    memory_file = root / MEMORY_REL
    before = memory_file.read_text(encoding="utf-8")

    data = json.loads(before)
    data["activation"] = {"state": "enforcing"}
    memory_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    broken = memory_file.read_text(encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])

    assert exit_code == 2
    assert memory_file.read_text(encoding="utf-8") == broken


def test_setup_on_schema_invalid_memory_fails_without_mutation(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    memory_file = root / MEMORY_REL
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {"name": "x", "description": "y"},
        "items": [],
        "examples": [],
        "decisions": [
            {
                "id": "bad",
                "decision": "bad rule",
                "rules": [{"type": "FORBID_DEPENDENCY", "value": "x"}],
            }
        ],
    }
    memory_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    original = memory_file.read_text(encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])

    assert exit_code == 2
    assert memory_file.read_text(encoding="utf-8") == original


def test_setup_never_downgrades_active_project(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    _write_memory_with_decisions(root)
    memory_file = root / MEMORY_REL

    data = json.loads(memory_file.read_text(encoding="utf-8"))
    data["activation"] = {
        "schema": "mneme.setup/v1",
        "state": "active",
        "setup_completed_at": "2026-01-01T00:00:00Z",
        "activated_at": "2026-02-01T00:00:00Z",
        "enforcement": "not_enabled",
    }
    memory_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    before = memory_file.read_text(encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert memory_file.read_text(encoding="utf-8") == before
    assert "remains in active mode" in captured.out
    assert "WARN" in captured.out


# ── G4: no protection-score inflation ────────────────────────────────────────

def test_setup_readiness_does_not_inflate_protection(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    _write_memory_with_decisions(root)
    monkeypatch.chdir(root)

    exit_code = main(["setup"])
    captured = capsys.readouterr()
    assert exit_code == 0

    # Frozen P1.2 semantics: Protected requires a FORBID_LITERAL typed rule.
    # The single-term anti-pattern decision (d_single_ap) is enforceable by
    # the core engine but is NOT existing protection: it must surface as
    # Mneme-ready, never as Protected, after setup.
    assert "Protected: 1" in captured.out
    assert "Mneme-ready: 1" in captured.out
    assert "Requires modelling: 1" in captured.out
    # The guidance decision plus the legacy "rule" item (migrated at load)
    # both classify as Guidance.
    assert "Guidance: 2" in captured.out

    # Setup is a pure view: decisions are untouched.
    after = json.loads((root / MEMORY_REL).read_text(encoding="utf-8"))
    by_id = {d["id"]: d for d in after["decisions"]}
    assert by_id["d_single_ap"]["anti_patterns"] == ["orm"]
    # Setup did not materialize a typed rule for the anti-pattern decision:
    # no guardrail generation happens implicitly (frozen M1.3 invariant).
    assert "rules" not in by_id["d_single_ap"]


def test_setup_does_not_write_any_enforcement_configuration(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    exit_code = main(["setup"])
    assert exit_code == 0

    data = _read_memory(root)
    assert data["activation"]["enforcement"] == "not_enabled"
    # No persisted enforcement-mode field exists anywhere in the document.
    assert "mode" not in json.dumps(data)


# ── G5: integration detection ────────────────────────────────────────────────

def test_setup_detects_all_supported_environments(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    for marker in (".claude", ".codex", ".kiro", ".cursor"):
        (root / marker).mkdir()

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Claude Code detected (.claude, native)" in captured.out
    assert "Codex CLI detected (.codex, native)" in captured.out
    assert "Kiro detected (.kiro, native)" in captured.out
    assert "Cursor detected (.cursor, rules export)" in captured.out

    record = _read_memory(root)["activation"]
    assert record["integrations_detected"] == [
        "claude_code", "codex_cli", "kiro", "cursor",
    ]
    assert record["integrations_configured"] == []


def test_setup_without_environments_reports_none(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    out = capsys.readouterr().out
    assert "None detected" in out
    assert _read_memory(root)["activation"]["integrations_detected"] == []


def test_detection_creates_no_files(tmp_path, monkeypatch):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    for marker in (".claude", ".codex", ".kiro", ".cursor"):
        assert not (root / marker).exists()


# ── Audit reference consumption (M1.3a scope) ────────────────────────────────

def test_setup_resolves_reference_and_records_baseline(tmp_path, monkeypatch, capsys, fake_pairing):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    exit_code = main(["setup", "--audit-ref", "ref-abc"])
    captured = capsys.readouterr()

    assert exit_code == 0
    record = _read_memory(root)["activation"]
    assert record["audit_ref"] == "ref-abc"
    baseline = record["baseline"]
    assert baseline["audit_id"] == RESOLVE_RESPONSE["audit_id"]
    assert baseline["project_id"] == RESOLVE_RESPONSE["project_id"]
    assert baseline["commit_sha"] == RESOLVE_RESPONSE["commit_sha"]
    assert baseline["mneme_version"] == RESOLVE_RESPONSE["mneme_version"]
    assert baseline["schema_version"] == RESOLVE_RESPONSE["schema_version"]
    assert baseline["audit_schema"] == "mneme.audit/v1"
    assert baseline["summary"] == RESOLVE_RESPONSE["summary"]
    assert baseline["resolved_at"]
    # G7: setup completion reported back to the Audit service.
    assert fake_pairing.complete_calls[0]["reference"] == "ref-abc"
    assert fake_pairing.complete_calls[0]["mneme_version"]
    assert baseline["completion"]["reported_at"]
    assert "Connected: contract-fixture (example/contract-fixture)" in captured.out
    assert "Setup recorded with the Audit service" in captured.out


def test_setup_without_audit_ref_reports_not_connected(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    out = capsys.readouterr().out
    assert "Not connected" in out


def test_setup_rejects_unknown_activation_schema(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    _write_memory_with_decisions(root)
    memory_file = root / MEMORY_REL

    data = json.loads(memory_file.read_text(encoding="utf-8"))
    data["activation"] = {"schema": "mneme.setup/v9", "state": "setup"}
    memory_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    before = memory_file.read_text(encoding="utf-8")

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "unsupported" in captured.err
    # A future schema must never be silently rewritten to the current one.
    assert memory_file.read_text(encoding="utf-8") == before


def test_setup_with_adr_dir_on_fresh_repo_succeeds(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    adr_dir = root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001-choice.md").write_text(
        "# ADR-001: choice\n\n## Decision\n\nUse JSON.\n", encoding="utf-8"
    )

    monkeypatch.chdir(root)
    exit_code = main(["setup"])
    captured = capsys.readouterr()

    assert exit_code == 0
    # Diagnostics are warn-only and never block setup.
    assert "ADR diagnostics" in captured.out
    assert "Mneme is installed in setup mode." in captured.out
    assert _read_memory(root)["activation"]["state"] == "setup"


def test_setup_rejects_empty_audit_ref(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    exit_code = main(["setup", "--audit-ref", "   "])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "ERROR" in captured.err
    assert not (root / MEMORY_REL).exists()


def test_setup_rejects_whitespace_audit_ref(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    exit_code = main(["setup", "--audit-ref", "bad ref with spaces"])
    assert exit_code == 2
    assert not (root / MEMORY_REL).exists()


def test_setup_rejects_overlong_audit_ref(tmp_path, monkeypatch):
    from mneme.setup import MAX_AUDIT_REF_LENGTH

    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    exit_code = main(["setup", "--audit-ref", "x" * (MAX_AUDIT_REF_LENGTH + 1)])
    assert exit_code == 2
    assert not (root / MEMORY_REL).exists()


def test_setup_preserves_existing_baseline_when_rerun_without_ref(tmp_path, monkeypatch, capsys, fake_pairing):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    assert main(["setup", "--audit-ref", "keep-me"]) == 0
    fake_pairing.resolve_calls.clear()
    exit_code = main(["setup"])
    captured = capsys.readouterr()
    assert exit_code == 0

    record = _read_memory(root)["activation"]
    assert record["audit_ref"] == "keep-me"
    # No network activity on a plain rerun; the connected baseline survives.
    assert fake_pairing.resolve_calls == []
    assert record["baseline"]["audit_id"] == RESOLVE_RESPONSE["audit_id"]
    assert "Connected: contract-fixture" in captured.out


# ── Pairing failure safety (G3) ───────────────────────────────────────────────

def test_setup_invalid_reference_fails_closed_before_writes(tmp_path, monkeypatch, capsys, fake_pairing):
    root = _make_repo(tmp_path)
    fake_pairing.resolve_error = "Setup reference has expired."
    monkeypatch.chdir(root)

    exit_code = main(["setup", "--audit-ref", "expired-ref"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "expired" in captured.err
    assert not (root / MEMORY_REL).exists()
    assert not (root / ".mneme").exists()


def test_setup_invalid_reference_on_existing_project_leaves_it_untouched(
    tmp_path, monkeypatch, fake_pairing
):
    root = _make_repo(tmp_path)
    _write_memory_with_decisions(root)
    memory_file = root / MEMORY_REL
    before = memory_file.read_text(encoding="utf-8")
    fake_pairing.resolve_error = "Unknown setup reference"

    monkeypatch.chdir(root)
    exit_code = main(["setup", "--audit-ref", "unknown"])

    assert exit_code == 2
    assert memory_file.read_text(encoding="utf-8") == before


def test_setup_incomplete_resolution_payload_fails_closed(tmp_path, monkeypatch, capsys, fake_pairing):
    root = _make_repo(tmp_path)
    fake_pairing.resolve_response = {"audit_id": "x"}  # no project_id/commit_sha
    monkeypatch.chdir(root)

    exit_code = main(["setup", "--audit-ref", "ref-abc"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "incomplete" in captured.err
    assert not (root / MEMORY_REL).exists()


def test_setup_completion_report_failure_warns_but_setup_succeeds(
    tmp_path, monkeypatch, capsys, fake_pairing
):
    root = _make_repo(tmp_path)
    fake_pairing.complete_error = "service unavailable"
    monkeypatch.chdir(root)

    exit_code = main(["setup", "--audit-ref", "ref-abc"])
    captured = capsys.readouterr()

    assert exit_code == 0
    record = _read_memory(root)["activation"]
    assert record["baseline"]["completion"] is None
    assert "could not be recorded" in captured.out


def test_setup_rerun_retries_pending_completion(tmp_path, monkeypatch, fake_pairing):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)

    fake_pairing.complete_error = "service unavailable"
    assert main(["setup", "--audit-ref", "ref-abc"]) == 0
    assert _read_memory(root)["activation"]["baseline"]["completion"] is None

    fake_pairing.complete_error = None
    exit_code = main(["setup"])
    assert exit_code == 0

    record = _read_memory(root)["activation"]
    assert record["baseline"]["completion"]["reported_at"]
    assert len(fake_pairing.complete_calls) == 2


def test_setup_complete_receives_origin_remote(tmp_path, monkeypatch, fake_pairing):
    root = tmp_path / "real-repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/contract-fixture.git"],
        cwd=root, check=True,
    )
    monkeypatch.chdir(root)

    exit_code = main(["setup", "--audit-ref", "ref-abc"])
    assert exit_code == 0
    assert fake_pairing.complete_calls[0]["repository"] == (
        "https://github.com/example/contract-fixture.git"
    )


def test_setup_offline_mode_records_reference_verbatim(tmp_path, monkeypatch):
    """pairing=None records the opaque reference without resolution."""
    from mneme.setup import run_setup

    root = _make_repo(tmp_path)
    outcome = run_setup(root=root, audit_ref="opaque-token", pairing=None)

    assert outcome.state == "setup"
    assert outcome.baseline is None
    record = _read_memory(root)["activation"]
    assert record["audit_ref"] == "opaque-token"
    assert record["baseline"] is None


def test_setup_without_audit_ref_never_calls_pairing(tmp_path, monkeypatch, capsys, fake_pairing):
    root = _make_repo(tmp_path)
    monkeypatch.chdir(root)
    assert main(["setup"]) == 0
    out = capsys.readouterr().out
    assert "Not connected" in out
    assert fake_pairing.resolve_calls == []
    assert fake_pairing.complete_calls == []
