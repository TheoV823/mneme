# M1.3 — Audit-to-Setup Activation: Execution Log

Contract: `docs/plans/m1-3-audit-to-setup-activation.md` (frozen).

## Current increment
M1.3b — Audit baseline pairing (CLI side; site side in mnemehq-site#104)

## Status
IN PROGRESS (M1.3a PR open: MnemeHQ/mneme#345; M1.3b CLI PR stacked on it)

## Completed
### M1.3a (PR MnemeHQ/mneme#345)
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
  Requires modelling / Guidance mapped from `assess_governance` semantics.
  Protected requires typed FORBID_LITERAL evidence.
- Integration detection (`mneme/integrations/detect.py`): Claude Code,
  Codex CLI, Kiro, Cursor. Detection only; never writes configuration,
  never enables enforcement.
- Extracted shared ADR diagnostics collection to `mneme/adr_diagnostics.py`.
- README: setup-mode section.

### M1.3b (this branch + MnemeHQ/mnemehq-site#104)
- `mneme/audit_pairing.py`: stdlib-only client for the Audit service —
  `resolve(reference)` (non-consuming) and `complete(reference, repository,
  mneme_version)` (idempotent server-side); base URL from
  `MNEME_AUDIT_API_URL` (default production Cloud Run URL).
- `mneme setup --audit-ref REF` now REQUIRES resolution before any local
  write: unknown/expired/mismatched/unreachable → fail-closed ERROR, no
  mutation (G3). Resolved baseline provenance (whitelisted keys only) is
  recorded in `activation.baseline`.
- Setup completion is reported back to the Audit service after the local
  write; a failed report leaves completion pending with a warning and is
  retried automatically on the next `mneme setup` run (G7).
- Local `git remote get-url origin` is passed to completion for the
  server-side repository mismatch check.
- Site backend (mnemehq-site#104): `setup_references` table, reference
  issuance/resolution/completion endpoints, project `activation_state`
  (`not_installed`/`setup`/`active` distinct from Audit lifecycle),
  migration 002.

## Current work
- M1.3c — Audit activation UI (mnemehq-site frontend), after M1.3a/M1.3b
  contracts are stable.

## Acceptance gates
- G1 (safe setup): PASS — M1.3a tests unchanged and passing
  (`test_setup_fresh_repo_initializes_in_setup_mode`,
  `test_setup_creates_nothing_but_mneme_state`); pairing adds no
  enforcement anywhere.
- G2 (idempotency / existing projects): PASS — byte-identical no-op rerun,
  existing project preservation, corrupt/invalid memory fail-safe tests;
  rerun preserves first-completion timestamps.
- G3 (audit linking): PASS — CLI: `test_setup_resolves_reference_and_records_baseline`
  (provenance preserved: audit, project, commit SHA, Mneme version, schema
  version), `test_setup_invalid_reference_fails_closed_before_writes`,
  `test_setup_invalid_reference_on_existing_project_leaves_it_untouched`,
  `test_setup_incomplete_resolution_payload_fails_closed`; site:
  issuance requires saved baseline, 404 unknown / 410 expired / 409
  mismatched repository (mnemehq-site#104 tests).
- G4 (no protection-score inflation): PASS — readiness remains a pure view;
  pairing records state only; site tests assert audit payload immutability
  after completion.
- G5 (integration detection): PASS — M1.3a detection tests unchanged.
- G6 (audit UI activation state): PARTIAL — API surface done (project
  endpoint exposes `activation_state`/`setup_completed_at`/`setup_audit_id`);
  UI lands in M1.3c.
- G7 (funnel attribution): PASS (recording + CLI reporting) —
  `test_complete_receives_origin_remote`, completion retry
  (`test_setup_rerun_retries_pending_completion`); site records
  setup_audit_id/setup_completed_at/redeemed_mneme_version.
- G8 (existing-product regression): PASS — full suite 1212 passed, 6
  skipped (reconciled M1.3a + M1.3b on P1.2 main); frozen benchmark runs
  byte-identical to `main` (no enforcement/retrieval code touched).

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
- M1.3a does not configure integrations (contract: setup MAY configure
  non-blocking integration behavior; choosing detect-only minimizes risk of
  implicit enforcement; hooks default to strict and must never be installed
  implicitly).
- Invalid audit refs (empty/whitespace/overlong) fail closed before any
  write; resolution semantics build on the same guardrails.
- Resolution is fail-closed and REQUIRED when `--audit-ref` is supplied via
  the CLI: an unverifiable reference is never recorded (contract §4 G3).
  `run_setup(pairing=None)` keeps verbatim recording for offline/embedded
  use and is covered by tests.
- Baseline provenance is whitelisted from the resolution payload — the raw
  server response is never persisted.
- Completion reporting happens after the local write; failure degrades to a
  warning with automatic retry on next run (server-side completion is
  idempotent via `already_redeemed`).
- Rerun without a reference preserves the previously connected baseline and
  performs no network calls.

## Verification
- New tests: `tests/test_cli_setup.py` pairing section (10 tests) +
  updated ref tests; `tests/test_setup_state.py` unchanged (20).
- Full repository suite: `python -m pytest -q` → 1212 passed, 6 skipped
  (rebased on P1.2 main; includes the setup/audit parity tests).
- Site-side verification in mnemehq-site#104 (backend 89 passed, 3
  skipped; root 2; scripts 60).
- Worktree context verified via `scripts/check_worktree_context.py`.

## Escalations
None

