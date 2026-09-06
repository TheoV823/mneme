# M1.4 — Protection Activation (P0)

## Status

Implemented.

## Mission

Close the first complete Mneme product loop:

```text
Audit → Setup → candidate → validate → activate → canonical verify → Protected
```

M1.4 turns an already-classified Mneme-ready architectural decision into a real,
verifiable deterministic protection. It is an activation layer over the frozen
P1.2 Architecture Protection Audit semantics — not a new classifier, not a new
rule language, and not an enforcement engine.

## Frozen semantics consumed (not reinterpreted)

- `mneme.enforcer.assess_protection` / `generate_protection_report` remain the
  single source of truth for Protected / Mneme-ready / Requires modelling /
  Guidance tiers.
- `mneme.readiness` remains a thin view over the canonical assessment; Audit
  and Setup classification parity is unchanged.
- The typed rule vocabulary stays `FORBID_LITERAL` (ADR-019) with ADR-020 path
  applicability; activation proposes no new rule type, no path selectors.
- Guidance decisions stay outside the protection denominator; superseded /
  deprecated decisions never count.
- Conservative multi-term ambiguity handling is untouched.

Core invariant:

> A decision does NOT become Protected because Mneme generated a rule,
> validated a rule, or recorded an activation. It becomes Protected only when
> the canonical protection assessment can observe real mechanical enforcement
> evidence in the repository.

## Lifecycle (derived, not stored)

```text
candidate → validated → activated → verified
```

No persistent per-decision lifecycle state is created. Final truth is always
re-derived from repository evidence:

- the installed typed rule in the decision's memory record is the enforcement
  artifact (enforced by the existing `mneme check` / hook path);
- the canonical assessment independently observes it and classifies Protected;
- activation metadata (the `activation` record) stays separate from protection
  truth and only carries the M1.3 `setup → active` state transition that
  M1.3 reserved for exactly this explicit user action.

## CLI surface

```bash
mneme protect list                 # Mneme-ready activation candidates
mneme protect status <id>          # canonical status of one decision
mneme protect validate <decision-id>   # deterministic dry validation
mneme protect activate <decision-id>   # explicit activation + canonical verify
```

All subcommands take `--memory <project_memory.json>` (required) and optional
`--repo-root <dir>` for the same external CI-evidence scan `mneme audit`
performs. Exit codes: `0` success / desired state; `1` actionable failure
(not eligible, validation failed, verification failed); `2` usage error
(missing file, unknown decision id, refused unsafe record).

## Activation mechanics

`activate` performs, in order:

1. canonical eligibility precheck (frozen P1.2 semantics only);
2. deterministic validation of the proposed rule against the existing
   enforcement engine (`check_prompt`); failure writes nothing;
3. idempotent install: the typed rule is appended to the decision's
   `rules[]` record in `project_memory.json` via raw read-modify-write
   (atomic, everything else preserved verbatim); an identical existing rule
   is left alone; a `setup`-state activation record transitions to `active`;
   unsupported/invalid records are refused before any write;
4. verification: reload from disk and re-run the canonical assessment.
   Only an independently observed Protected tier is reported as verified.

Result distinctions (never faked):

- `verified` — artifact installed (now or earlier) and canonical assessment
  observes Protected;
- `already_protected` — canonical assessment already observed Protected;
  nothing written;
- `verification_failed` — artifact written but canonical assessment did not
  observe Protected: the decision remains NOT Protected (exit 1);
- `validation_failed` — validation rejected the proposal; nothing written;
- `not_eligible` — Requires-modelling, Guidance, superseded/inactive, or
  already-Protected decisions are not activation candidates.

## Acceptance gates

| Gate | Status |
| --- | --- |
| G1 — Canonical readiness | PASS: eligibility via `activation_precheck` over `assess_protection` only (`tests/test_protection_activation.py`) |
| G2 — No implicit enforcement | PASS: audit/setup/discovery/validation file-equality tests |
| G3 — Deterministic validation | PASS: four engine-backed checks, no model judgment |
| G4 — Explicit activation | PASS: only `protect activate` writes; idempotency + refusal tests |
| G5 — Correct applicability | PASS: enforcement/exemption tests incl. canonical policy source |
| G6 — Evidence before score | PASS: no-evidence activation leaves Current Protection unchanged |
| G7 — Re-audit parity | PASS: fresh audit + setup observe the same Protected classification |
| G8 — Regression safety | PASS: full suite green (1237 passed, 6 skipped) |

## Verification

```bash
python -m pytest tests/test_protection_activation.py   # new M1.4 tests
python -m pytest tests                                 # full suite
```

## Out of scope (unchanged from the milestone contract)

LLM-generated rules, Requires-modelling conversion, automatic ADR generation,
protection during install/setup, bulk activation, approvals, RBAC,
organizations, billing, hosted source access, cloud execution, drift
monitoring, migration functionality, conflict resolution, remediation of
existing violations, rule-authoring UI, site UX.

## Known limitations (deliberate)

- Legacy-migrated decisions (derived from `items[]`, not `decisions[]`) are
  not activatable — there is no raw record to attach a rule to; activation
  fails closed with a clear error.
- Only the canonical proposal shape (a global `FORBID_LITERAL` token) is
  activation-ready; scoped rules return `unsupported` from validation.
- Activation flips the project `activation` record `setup → active` only when
  that record exists; projects without one gain no invented record.
- No `--json` output for `protect` (P0 is the human workflow; `mneme audit
  --json` remains the machine surface).
