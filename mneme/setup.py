"""
setup.py — The ``mneme setup`` flow (M1.3a).

Initializes Mneme project state in *setup mode* under the frozen M1.3
contract (docs/plans/m1-3-audit-to-setup-activation.md):

- setup NEVER enables blocking enforcement;
- setup NEVER classifies a decision as Protected that lacks typed-rule
  enforcement evidence (readiness is a pure view — see mneme.readiness);
- setup NEVER mutates application code, unrelated configuration, or existing
  memory content beyond adding the ``activation`` record;
- setup is idempotent: rerunning with no material change writes nothing;
- an ``active`` project is left untouched by setup (no silent downgrade).

All validation happens before the first write, so any pre-execution failure
leaves the repository exactly as it was.

Audit reference handling in M1.3a: ``--audit-ref`` is consumed and recorded
verbatim as an opaque string. Resolution against the Architecture Audit
service is the M1.3b pairing mechanism; recording an opaque reference is
inert — no enforcement or classification follows from it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from mneme.adr_diagnostics import collect_adr_diagnostics
from mneme.integrations.detect import DetectedIntegration, detect_integrations
from mneme.memory_store import MemoryStore
from mneme.enforcer import ProtectionTier
from mneme.readiness import readiness_counts
from mneme.setup_state import (
    DEFAULT_MEMORY_PATH,
    ACTIVATION_SCHEMA,
    ENFORCEMENT_NOT_ENABLED,
    ActivationRecord,
    ActivationStateError,
    STATE_ACTIVE,
    STATE_NOT_INSTALLED,
    STATE_SETUP,
    atomic_write_json,
    derive_activation_state,
    scaffold_project_memory,
    utc_now,
    write_activation,
)

GIT_MARKER = ".git"
DEFAULT_ADR_DIR = "docs/adr"

# The reference is opaque, but it must be a sane opaque token: a single
# non-empty chunk with no internal whitespace and a bounded length. Any real
# reference format introduced by M1.3b pairing must remain valid under these
# constraints.
MAX_AUDIT_REF_LENGTH = 256
_AUDIT_REF_PATTERN = re.compile(r"^\S+$")


class SetupError(Exception):
    """A pre-execution setup failure. No filesystem mutation has occurred."""


@dataclass
class SetupOutcome:
    """Everything the CLI needs to render the setup summary."""

    project_root: Path
    memory_path: Path
    created_memory: bool
    previous_state: str
    state: str
    rerun: bool
    audit_ref: str
    integrations: list[DetectedIntegration] = field(default_factory=list)
    decision_count: int = 0
    readiness: dict[ProtectionTier, int] = field(default_factory=dict)
    adr_diagnostics: int = 0
    adr_diagnostics_present: bool = False
    warnings: list[str] = field(default_factory=list)


def find_project_root(start: Path) -> Path | None:
    """Walk up from ``start`` to the nearest git repository root.

    Handles both ``.git`` directories and ``.git`` files (linked worktrees).
    """
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / GIT_MARKER).exists():
            return candidate
    return None


def mneme_version() -> str:
    """Best-effort version of the running Mneme distribution."""
    import importlib.metadata

    try:
        return importlib.metadata.version("mneme-hq")
    except importlib.metadata.PackageNotFoundError:
        pass
    marker = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if marker.exists():
        match = re.search(
            r'^version\s*=\s*"([^"]+)"', marker.read_text(encoding="utf-8"), re.M
        )
        if match:
            return match.group(1)
    return "unknown"


def validate_audit_ref(audit_ref: str) -> str:
    """Validate an opaque audit reference supplied on the command line."""
    ref = audit_ref.strip()
    if not ref:
        raise SetupError("audit reference must not be empty")
    if len(ref) > MAX_AUDIT_REF_LENGTH:
        raise SetupError(
            f"audit reference exceeds {MAX_AUDIT_REF_LENGTH} characters"
        )
    if not _AUDIT_REF_PATTERN.match(ref):
        raise SetupError("audit reference must not contain whitespace")
    return ref


def _load_validated_decisions(memory_path: Path) -> list:
    """Load an existing memory file, failing safely if it is invalid.

    A file that raw JSON parsing accepts but MemoryStore rejects is broken
    for every other Mneme surface; setup must not paper over it by writing
    an activation record into it.
    """
    store = MemoryStore(memory_path)
    try:
        store.load()
    except Exception as exc:
        raise SetupError(
            f"existing memory file {memory_path} failed validation: {exc}"
        ) from exc
    return store.decisions()


def run_setup(
    root: Path | None = None,
    memory: Path | None = None,
    audit_ref: str = "",
) -> SetupOutcome:
    """Run the setup flow and return its outcome.

    Raises :class:`SetupError` before any write on invalid context. On
    success the repository contains a project memory with an activation
    record in ``setup`` state and nothing else has changed.
    """
    start = Path(root) if root is not None else Path.cwd()
    project_root = find_project_root(start)
    if project_root is None:
        raise SetupError(
            f"no git repository found above {start} — "
            "Mneme setup requires a repository context"
        )

    if memory is not None:
        memory_path = Path(memory)
        if not memory_path.is_absolute():
            memory_path = Path.cwd() / memory_path
    else:
        memory_path = project_root / DEFAULT_MEMORY_PATH

    ref = validate_audit_ref(audit_ref) if audit_ref.strip() else ""

    integrations = detect_integrations(project_root)

    created_memory = not memory_path.exists()
    previous_record: ActivationRecord | None = None
    if created_memory:
        previous_state: str = STATE_NOT_INSTALLED
        document = scaffold_project_memory(created_by="mneme setup")
        document["meta"]["name"] = project_root.name
        document["meta"]["description"] = (
            f"Architecture memory for {project_root.name}, created by mneme setup"
        )
        decisions: list = []
    else:
        with open(memory_path, encoding="utf-8") as f:
            try:
                raw_document = json.load(f)
            except json.JSONDecodeError as exc:
                raise SetupError(
                    f"existing memory file {memory_path} is not valid JSON: {exc}"
                ) from exc
        raw_activation = raw_document.get("activation")
        if raw_activation is not None:
            if raw_activation.get("schema") not in (None, ACTIVATION_SCHEMA):
                raise SetupError(
                    f"activation record in {memory_path} uses unsupported "
                    f"schema {raw_activation.get('schema')!r}; refusing to "
                    "modify it"
                )
            try:
                previous_record = ActivationRecord.from_dict(raw_activation)
            except ActivationStateError as exc:
                raise SetupError(
                    f"existing activation record in {memory_path} is invalid: {exc}"
                ) from exc
        previous_state = (
            previous_record.state if previous_record is not None else STATE_SETUP
        )
        decisions = _load_validated_decisions(memory_path)

    outcome = SetupOutcome(
        project_root=project_root,
        memory_path=memory_path,
        created_memory=created_memory,
        previous_state=previous_state,
        state=previous_state,
        rerun=False,
        audit_ref=ref,
        integrations=integrations,
        decision_count=len(decisions),
        # P1.2 frozen semantics with CI-evidence scanning over this
        # repository — exactly what `mneme audit --repo-root` reports.
        readiness=readiness_counts(decisions, repo_root=project_root),
    )

    record = ActivationRecord(
        state=STATE_SETUP,
        mneme_version=mneme_version(),
        setup_started_at=(
            previous_record.setup_started_at
            if previous_record is not None and previous_record.setup_started_at
            else utc_now()
        ),
        setup_completed_at=(
            previous_record.setup_completed_at
            if previous_record is not None and previous_record.setup_completed_at
            else utc_now()
        ),
        audit_ref=ref
        if ref
        else (previous_record.audit_ref if previous_record is not None else ""),
        baseline=None,
        integrations_detected=[i.key for i in integrations],
        integrations_configured=[],
        enforcement=ENFORCEMENT_NOT_ENABLED,
    )

    if previous_state == STATE_ACTIVE:
        # Never silently downgrade an explicitly activated project. Setup
        # re-reports status and leaves the record untouched.
        outcome.state = STATE_ACTIVE
        outcome.rerun = True
        outcome.warnings.append(
            "project is in active state; setup did not change activation"
        )
        _attach_adr_diagnostics(outcome)
        return outcome

    outcome.state = STATE_SETUP
    outcome.rerun = previous_record is not None
    # The summary reports the effective persisted reference, which preserves
    # a previously recorded audit_ref when the rerun omits --audit-ref.
    outcome.audit_ref = record.audit_ref

    if created_memory:
        document["activation"] = record.to_dict()
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(memory_path, document)
    else:
        existing = (
            previous_record.to_dict() if previous_record is not None else None
        )
        if existing != record.to_dict():
            write_activation(memory_path, record)

    # ADR diagnostics run after the memory is on disk so they observe the
    # post-setup state (and a freshly created memory file does exist).
    _attach_adr_diagnostics(outcome)
    return outcome


def _attach_adr_diagnostics(outcome: SetupOutcome) -> None:
    adr_dir = outcome.project_root / DEFAULT_ADR_DIR
    if not adr_dir.is_dir():
        return
    outcome.adr_diagnostics = len(
        collect_adr_diagnostics(memory_path=outcome.memory_path, adr_dir=adr_dir)
    )
    outcome.adr_diagnostics_present = True
