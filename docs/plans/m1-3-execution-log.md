# M1.3 — Audit-to-Setup Activation: Execution Log

Contract: `docs/plans/m1-3-audit-to-setup-activation.md` (frozen).

## Current increment
M1.3a — Setup state + CLI

## Status
IN PROGRESS (PR open)

## Completed
- Activation state model (`mneme/setup_state.py`): `not_installed → setup → active`,
  persisted as an optional top-level `activation` key in the existing
  `.mneme/project_memory.json` (no parallel state file; all existing writers
  do raw read-modify-write and preserve unknown keys).
- `mneme setup` CLI command (`mneme/setup.py` + `mneme/cli.py`):
  git-repository context check, initialization of project memory when
  required (scaffold reuses the init scaffold), memory validation, agent
  environment detection (read-only), readiness view, setup summary,
  idempotent reruns.
- Readiness view (`mneme/readiness.py`): Protected / Mneme-ready /
  Requires modelling / Guidance mapped from `assess_governability`.
  Protected requires typed FORBID_LITERAL evidence.
- Integration detection (`mneme/integrations/detect.py`): Claude Code,
  Codex CLI, Kiro, Cursor. Detection only; never writes configuration,
  never enables enforcement.
- `--audit-ref` consumed and recorded verbatim as an opaque string.
  Resolution/pairing is M1.3b (not implemented yet).
- Extracted shared ADR diagnostics collection to `mneme/adr_diagnostics.py`
  (used by both `check` and `setup`; no behavior change).
- README: setup-mode section.

## Current work
- PR for M1.3a; then M1.3b (Audit baseline pairing in mnemehq-site backend
  + CLI resolution).

## Acceptance gates
- G1 (safe setup): PASS — `test_setup_fresh_repo_initializes_in_setup_mode`
  (fresh git repo → state `setup`, `enforcement: "not_enabled"`,
  `activated_at: null`), `test_setup_creates_nothing_but_mneme_state`
  (only `.mneme/project_memory.json` added),
  `test_setup_does_not_touch_existing_agent_configuration`.
- G2 (idempotency / existing projects): PASS —
  `test_setup_rerun_is_byte_identical`,
  `test_setup_existing_project_preserves_all_content`,
  `test_setup_rerun_on_existing_project_preserves_first_completion`,
  `test_setup_on_corrupt_memory_fails_without_mutation`,
  `test_setup_on_schema_invalid_memory_fails_without_mutation`,
  `test_setup_on_invalid_activation_record_fails_without_mutation`.
- G3 (audit linking): NOT YET APPLICABLE — M1.3b.
- G4 (no protection-score inflation): PASS —
  `test_readiness_single_term_anti_pattern_is_not_protected`,
  `test_setup_readiness_does_not_inflate_protection` (setup-only run keeps
  Mneme-ready as Mneme-ready; no rule materialization);
  readiness is a pure view over `assess_governability`.
- G5 (integration detection): PASS —
  `test_setup_detects_all_supported_environments`,
  `test_setup_without_environments_reports_none`,
  `test_detection_creates_no_files` (detection activates nothing).
- G6 (audit UI activation state): NOT YET APPLICABLE — M1.3c.
- G7 (funnel attribution): NOT YET APPLICABLE — M1.3b/d.
- G8 (existing-product regression): PASS — full suite
  `1179 passed, 6 skipped` (baseline suite, worktree HEAD), frozen
  benchmark runs `examples/benchmarks` and
  `examples/benchmarks-enforcement-quality` byte-identical to `main`
  (exit 0 both, same verdicts).

## Implementation decisions
- Activation state persisted inside `project_memory.json` (`activation` key)
  rather than a new file — contract section 7 requires reusing existing
  project metadata; verified every memory writer preserves unknown keys.
- **P1.2 reconciliation (post-merge of #346)**: readiness classification is
  NOT an independent interpretation. `mneme/readiness.py` delegates to the
  frozen P1.2 API (`assess_protection` / `generate_protection_report`),
  and setup passes the project root so the CI-evidence scan matches
  `mneme audit --repo-root`. Parity regression tests
  (`tests/test_setup_audit_parity.py`) pin that `mneme audit` and
  `mneme setup` agree on all four tier counts for the same
  memory/repository — including verified-CI upgrades and status
  (superseded/deprecated) exclusion — and that setup never upgrades
  anything beyond the audit.
- Legacy memory without an activation record derives as `setup` (Mneme
  present, enforcement never persisted as enabled); `not_installed` only
  when no memory file exists.
- Rerun with no material change performs no write (strongest idempotency);
  rerun with changes (e.g. new `--audit-ref`) preserves first-completion
  timestamps.
- Setup on an `active` project refuses to downgrade: leaves the record
  untouched and reports a warning (no silent state transitions).
- Readiness classification lives in core (`mneme/readiness.py`) and treats
  only typed FORBID_LITERAL rules as Protected — single-term anti-patterns
  (governability tier `enforceable`) remain Mneme-ready. This mirrors the
  frozen P1.2 mapping in the audit workspace and is the G4-critical choice.
- M1.3a does not configure integrations (contract: setup MAY configure
  non-blocking integration behavior; choosing detect-only minimizes risk of
  implicit enforcement; hooks default to strict and must never be installed
  implicitly).
- Invalid audit refs (empty/whitespace/overlong) fail closed before any
  write; M1.3b adds resolution semantics on top of the same guardrails.

## Verification
- New tests: `tests/test_setup_state.py` (20), `tests/test_cli_setup.py`
  (28) — all pass.
- Full repository suite: `python -m pytest -q` → 1179 passed, 6 skipped.
- Frozen benchmarks: `mneme benchmark examples/benchmarks` and
  `mneme benchmark examples/benchmarks-enforcement-quality` — output and
  exit codes identical to `main`.
- Worktree context verified via `scripts/check_worktree_context.py`.

## Escalations
None
