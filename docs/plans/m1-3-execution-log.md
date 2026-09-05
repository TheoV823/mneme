# M1.3 — Audit-to-Setup Activation: Execution Log

Contract: `docs/plans/m1-3-audit-to-setup-activation.md` (frozen).

## Current increment
Complete — all four increments implemented. Mneme-side stack merged;
site-side stack PR'd and awaiting merge.

## Status
MNEME-SIDE MERGED — site stack awaiting human merge

PRs:
1. MnemeHQ/mneme#345 — M1.3a: setup state + CLI — **MERGED** as 24dde857
   (includes the P1.2 reconciliation commit)
2. MnemeHQ/mneme#347 — M1.3b CLI: audit-ref resolution + completion —
   **MERGED** as c8c9f2b3 (rebased onto P1.2 main; full battery green)
3. MnemeHQ/mnemehq-site#104 — M1.3b site: setup references, activation
   state persistence, pairing endpoints — open, full battery green
4. MnemeHQ/mnemehq-site#105 — M1.3c: audit activation UI (stacked on #104)
5. MnemeHQ/mnemehq-site#106 — M1.3d: funnel instrumentation + pilot
   handoff (stacked on #105)
6. MnemeHQ/mneme#348 — this log (merged last)

## Completed
- **M1.3a (mneme#345)**: activation state model `not_installed → setup →
  active` persisted in `project_memory.json` (`activation` key, schema
  `mneme.setup/v1`); `mneme setup` (git context, init, memory validation,
  integration detection, readiness view, idempotent rerun); shared ADR
  diagnostics extraction.
- **P1.2 reconciliation (mneme#345, post-merge of #346)**:
  `mneme/readiness.py` is a thin view over the canonical P1.2 API
  (`assess_protection` / `generate_protection_report`) — no independent
  tier interpretation from `assess_governability`. Setup passes the
  project root so the CI-evidence scan matches `mneme audit --repo-root`.
  Parity regression tests (`tests/test_setup_audit_parity.py`) pin that
  `mneme audit` and `mneme setup` agree on all four tier counts for the
  same memory/repository — including verified-CI upgrades and status
  (superseded/deprecated) exclusion — and that setup never upgrades
  anything beyond the audit.
- **M1.3b (mneme#347 + site#104)**: opaque/scoped/expiring setup
  references (`setup_references` table, migration 002); issuance
  (saved-baseline required), resolution (provenance: audit, project,
  commit SHA, Mneme version, schema version), idempotent completion;
  project `activation_state`/`setup_completed_at`/`setup_audit_id`;
  CLI resolve-before-write (fail-closed), baseline recording, completion
  reporting with retry.
- **M1.3c (site#105)**: before-setup "Install Mneme" promise + on-demand
  copyable `pipx install "mneme-hq>=0.6.0"` / `mneme setup --audit-ref …`
  command; after-setup "Mneme installed — Setup mode" panel with honest
  checklist and "Start Pilot" CTA; active state rendered distinctly.
- **M1.3d (site#106)**: `audit_setup_recognized` event (existing GTM
  pipeline); `start_pilot` intent for the post-setup CTA; pilot handoff
  recorded via explicit lifecycle transition (attribution preserved,
  activation state untouched); funnel mapping documented in
  `docs/site/gtm-tagging-requirements.md`.

## Current work
None — M1.3 implementation complete. Post-merge of the site stack, the
deploy pipeline runs per its own lifecycle; deployment claims follow the
canonical evidence rule.

## Acceptance gates
- **G1 Safe setup: PASS** — fresh git repo → `mneme setup` exits 0,
  state `setup`, `enforcement: "not_enabled"`, `activated_at: null`, only
  `.mneme/project_memory.json` created (mneme#345:
  `test_setup_fresh_repo_initializes_in_setup_mode`,
  `test_setup_creates_nothing_but_mneme_state`).
- **G2 Idempotency / existing projects: PASS** — byte-identical no-op
  rerun; existing projects preserved content-for-content; corrupt/invalid
  memory fail-safe; active projects never downgraded (mneme#345/#347).
- **G3 Audit linking: PASS** — CLI resolves references before any write;
  invalid/expired/mismatched/unreachable fail closed with zero mutation
  (mneme#347); issuance requires saved baseline; 404/410/409 failure
  safety server-side (site#104).
- **G4 No protection-score inflation: PASS** — readiness delegates to the
  frozen P1.2 semantics (parity with `mneme audit` pinned by
  `tests/test_setup_audit_parity.py`); setup never materializes rules;
  pairing never mutates audit payloads (tests in #345/#347/#104).
- **G5 Integration detection: PASS** — Claude Code / Codex CLI / Kiro /
  Cursor detected read-only; detection creates nothing and activates
  nothing (mneme#345 tests).
- **G6 Audit UI activation state: PASS** — API + UI distinguish
  Not installed / Setup / Active; setup state exposes correct next action
  ("Start Pilot") (site#104 API tests, site#105 UI tests).
- **G7 Funnel attribution: PASS** — setup attributed via `setup_audit_id`
  + `setup_completed_at` + reference redemption; CLI reports completion
  with origin remote + Mneme version, retry on failure; pilot handoff
  recorded via explicit lifecycle transition with attribution intact
  (site#106 test); funnel events emitted/recorded per the existing
  analytics architecture.
- **G8 Existing-product regression: PASS** — reconciled mneme stack: full
  suite 1212 passed/6 skipped (P1.2 main baseline + M1.3 tests); frozen
  benchmark runs byte-identical to `main`; `mneme check --mode warn`
  PASS; site backend 90 passed/3 skipped, scripts 60 passed, root
  fixtures 2 passed; frontend 70 passed; CI green on #345, #347, #104
  (full batteries); existing M1/M1.2 behavior intact
  (`test_workspace_contract.py`, `test_m1_acceptance_gates.py` green).

## Implementation decisions
- Activation state persisted inside `project_memory.json` (`activation`
  key) — contract §7: reuse existing project metadata; verified every
  memory writer preserves unknown keys.
- Readiness classification is a thin P1.2 view (see reconciliation above);
  legacy pre-P1.2 governability semantics remain untouched in the core
  for runtime governability consumers.
- M1.3a detects integrations but configures none (hooks default strict;
  implicit hook installation would violate the core invariant).
- CLI `--audit-ref` resolution is required and fail-closed;
  `run_setup(pairing=None)` retains verbatim recording for
  offline/embedded use.
- Setup references: `secrets.token_urlsafe`, scoped to one audit+project,
  expiring (14d default), single-purpose; repository mismatch checked by
  normalized GitHub owner/repo (non-GitHub remotes skip rather than guess).
- Integration-detection checklist item deliberately omitted from the setup
  panel (no server-side detection data; no fabricated evidence, ADR-002
  discipline).
- Setup "recording pending" degrades gracefully: warning + automatic
  retry on next `mneme setup` (server completion is idempotent).

## Verification
- mneme repo (reconciled stack): `python -m pytest -q` → 1212 passed,
  6 skipped; `mneme benchmark examples/benchmarks` and
  `mneme benchmark examples/benchmarks-enforcement-quality` identical to
  `main`; CI full battery green on #345 and #347.
- mnemehq-site: backend 90 passed/3 skipped; root fixtures 2 passed;
  scripts 60 passed; frontend 70 passed + production build; CI full
  battery green on #104.
- Worktree context verified per repo policy for every task worktree.

## Escalations
None
