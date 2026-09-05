"""Parity regression (M1.3 reconciliation with canonical P1.2).

For the same project memory/repository, `mneme audit` and `mneme setup`
must agree on Protected / Mneme-ready / Requires modelling / Guidance
counts, and setup must never upgrade anything beyond the audit.
"""
import json
import re
from pathlib import Path

from mneme.cli import main

MEMORY_REL = Path(".mneme") / "project_memory.json"

DECISIONS = [
    {
        "id": "d_typed",
        "decision": "Store data in sqlite",
        "rationale": "embedded",
        "scope": ["storage"],
        "constraints": [],
        "anti_patterns": [],
        "rules": [{"type": "FORBID_LITERAL", "value": "sqlite"}],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": "d_ci",
        "decision": "No postgres in the service layer",
        "rationale": "",
        "scope": [],
        "constraints": [],
        "anti_patterns": ["postgres"],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": "d_single_ap",
        "decision": "Avoid ORM indirection",
        "rationale": "",
        "scope": [],
        "constraints": [],
        "anti_patterns": ["orm"],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": "d_single_no",
        "decision": "Keep config in JSON",
        "rationale": "",
        "scope": [],
        "constraints": ["no yaml"],
        "anti_patterns": [],
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
    {
        "id": "d_superseded",
        "decision": "Old config rule",
        "rationale": "",
        "scope": [],
        "constraints": [],
        "anti_patterns": [],
        "rules": [{"type": "FORBID_LITERAL", "value": "xml"}],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "status": "superseded",
    },
]

# Verified CI enforcement for the "postgres" token: a single-line guard
# whose failure is deterministically linked to detecting the token
# (frozen P1.2 verified linkage shape).
CI_WORKFLOW = """name: guard
on: [push]
jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - run: if grep -rq postgres src/; then exit 1; fi
"""


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    memory = root / MEMORY_REL
    memory.parent.mkdir(parents=True)
    memory.write_text(json.dumps({
        "meta": {"name": "parity", "description": "parity fixture"},
        "items": [],
        "examples": [],
        "decisions": DECISIONS,
    }, indent=2) + "\n", encoding="utf-8")
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "guard.yml").write_text(CI_WORKFLOW, encoding="utf-8")
    return root


def _setup_counts(out: str) -> dict[str, int]:
    counts = {}
    for key in ("Protected", "Mneme-ready", "Requires modelling", "Guidance"):
        match = re.search(rf"^\s*{re.escape(key)}: (\d+)$", out, re.M)
        assert match, f"setup summary missing {key}: {out}"
        counts[key] = int(match.group(1))
    return counts


def test_setup_and_audit_agree_on_tier_counts(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    audit_json = tmp_path / "audit.json"

    monkeypatch.chdir(root)
    exit_code = main([
        "audit", "--memory", str(root / MEMORY_REL),
        "--repo-root", str(root), "--json", str(audit_json),
    ])
    captured = capsys.readouterr()
    assert exit_code == 0, captured.out + captured.err
    summary = json.loads(audit_json.read_text(encoding="utf-8"))["summary"]

    capsys.readouterr()
    exit_code = main(["setup"])
    captured = capsys.readouterr()
    assert exit_code == 0
    setup_counts = _setup_counts(captured.out)

    audit_counts = {
        "Protected": summary["protected"],
        "Mneme-ready": summary["mneme_ready"],
        "Requires modelling": summary["requires_modelling"],
        "Guidance": summary["guidance"],
    }
    # Frozen P1.2 semantics are shared: setup must agree with the audit.
    assert setup_counts == audit_counts

    # Expected canonical values for this corpus: verified CI evidence
    # upgrades d_ci to protected; the superseded decision is provenance
    # only and never counted.
    assert audit_counts == {
        "Protected": 2,            # d_typed (typed rule) + d_ci (verified CI)
        "Mneme-ready": 2,          # d_single_ap + d_single_no
        "Requires modelling": 1,   # d_multi_ap
        "Guidance": 1,             # d_guidance
    }
    assert summary["total_decisions"] == 7
    assert summary["protection_relevant"] == 5

    # Setup must not upgrade anything beyond the audit.
    for key in audit_counts:
        assert setup_counts[key] <= audit_counts[key], key


def test_setup_agrees_with_audit_without_repo_root(tmp_path, monkeypatch, capsys):
    """Without CI evidence both views reduce to the same tiers."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".git").mkdir()
    memory = root / MEMORY_REL
    memory.parent.mkdir(parents=True)
    memory.write_text(json.dumps({
        "meta": {"name": "parity", "description": "parity fixture"},
        "items": [],
        "examples": [],
        "decisions": [d for d in DECISIONS if d["id"] not in ("d_ci", "d_superseded")],
    }, indent=2) + "\n", encoding="utf-8")
    audit_json = tmp_path / "audit.json"

    monkeypatch.chdir(root)
    exit_code = main(["audit", "--memory", str(memory), "--json", str(audit_json)])
    capsys.readouterr()
    assert exit_code == 0
    summary = json.loads(audit_json.read_text(encoding="utf-8"))["summary"]

    capsys.readouterr()
    assert main(["setup"]) == 0
    setup_counts = _setup_counts(capsys.readouterr().out)

    assert setup_counts == {
        "Protected": summary["protected"],
        "Mneme-ready": summary["mneme_ready"],
        "Requires modelling": summary["requires_modelling"],
        "Guidance": summary["guidance"],
    }
