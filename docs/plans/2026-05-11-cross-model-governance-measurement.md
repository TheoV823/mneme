# Cross-Model Governance Measurement v0.1 — Plan

**Status:** draft plan, docs-only. No code, fixtures, retrieval, or enforcement
behavior is changed by this document.
**Anchor commit:** Layer 1 freeze at `e73ff7d`
([`docs/architecture/layer1-freeze-e73ff7d.md`](../architecture/layer1-freeze-e73ff7d.md))
**Authority source:** `.mneme/project_memory.json`, ADRs in `docs/adr/`, the
Layer 1 freeze document, the Step 3C charter
([`docs/plans/2026-05-09-step-3c-retrieval-tuning-charter.md`](2026-05-09-step-3c-retrieval-tuning-charter.md)).

---

## 1. Context

Layer 1 is frozen at `e73ff7d`. The freeze document records:

- Benchmark version v1.1, stabilization complete through Step 3C.
- 7/7 PASS, recall@3 = 1.00, recall@1 = 5/5 = 1.00, precision@3 = 0.333,
  irrelevant injection rate = 100% — all structurally pinned.
- Exit criteria 1 ("benchmark integrity stabilized") and 2 ("deterministic
  enforcement validated") are met. Exit criteria 3 (real-world drift
  prevention), 4 (design-partner validation), and 5 (wedge validated) are open.

The next legitimate measurement work is **not** another retrieval pass and
**not** an expansion of the Layer 1 fixture suite. Both would violate the
freeze and the Step 3C anti-overfitting charter.

What is missing is comparative evidence: how often AI coding agents drift from
architectural decisions **without** Mneme, and how much that drift is reduced
**with** Mneme. The frozen Layer 1 benchmark contract is the right substrate
for that comparison — it is deterministic, fixture-based, auditable, and the
enforcement boundary is byte-stable.

This plan opens a separate measurement track on top of that frozen contract.

---

## 2. Goal

Produce a reproducible, citable measurement of architectural drift across
multiple AI coding agents, runtimes, and models, using the frozen Layer 1
benchmark as the governance substrate.

The headline question this track is built to answer:

> Given identical architectural decisions and identical prompts, how often
> does each (model, runtime) pair produce output that violates a recorded
> decision — with governance off, and with Mneme governance on?

This track does **not** try to answer:

- Which model is "better" in general.
- Which agent harness is "better" in general.
- Whether Mneme retrieves the right decision (that is Layer 1's job, already
  proven at `e73ff7d`).

---

## 3. Relationship to the Layer 1 freeze

The Layer 1 freeze is an **input contract** to this track, not a target.

This plan inherits, without modification:

- The 11-decision retrieval pool.
- K = 3 as `DEFAULT_MAX_DECISIONS`.
- The five Decision-field scoring weights, stopword filter, length floor, and
  insertion-order tiebreak.
- The 7 shipped fixture scenarios under
  [`examples/benchmarks/`](../../mneme-project-memory/examples/benchmarks/).
- The five-verdict Layer 2 semantics (`PASS`, `FAIL`, `WEAK`,
  `WEAK_RETRIEVAL`, `MALFORMED`).
- The suite-level metric definitions and the `governed` aggregation filter.
- The "no `acceptable_decision_ids` mutation for headline movement" rule from
  the Step 3C charter.

If any of those need to change for this track to function, this track is
wrong, not the freeze. The fix is to redesign the track, not amend the freeze.

The freeze's amendment procedure (Layer 1 §Amendment Procedure) is not the
entry point for this work.

---

## 4. Scope of v0.1

### 4.1 In scope

- Designing a **measurement protocol** that consumes the Layer 1 fixture set
  and produces per-(model, runtime, governance-mode) metrics.
- Defining the metrics in §6 and their exact computation.
- Defining what counts as a "violation" in terms of the existing Layer 2
  verdict logic, so a violation is the same object the frozen benchmark
  already recognises.
- Specifying the set of (model, runtime) pairs to evaluate in v0.1 (§5).
- Specifying repeatability requirements (§7).
- Specifying the reporting surface — where results live, how they are versioned,
  and what cannot be silently changed once published (§8).

### 4.2 Out of scope (v0.1)

These are out of scope for v0.1 and require a separate plan, ADR, or charter
amendment before being pulled in:

- Any change to retrieval, enforcement, fixtures, K, scoring weights, metric
  formulas, verdict logic, or the governed aggregation filter (frozen).
- Adding scenarios to the Layer 1 suite (frozen; §4.4 of Step 3C charter).
- Populating `acceptable_decision_ids` to move precision or irrelevant
  injection rate (gameable surface; explicitly off-limits per Step 3C §5).
- Live model calls inside the Layer 1 benchmark harness. v0.1 keeps the
  Layer 1 benchmark deterministic and canned; cross-model calls happen in a
  **separate** evaluation runner that consumes Layer 1 outputs.
- Quality scoring of generated code beyond the existing Layer 2 verdict
  surface. Layer 1 is governance-first; this track inherits that discipline.
- Auto-fix, remediation, or rewrite of generated output. Mneme blocks; humans
  or LLMs fix.
- Any GTM, pricing, customer, or internal-strategy framing of results. Per
  repo CLAUDE.md, that content does not belong in this repo.

### 4.3 Anti-goals

These are stated explicitly so they do not creep in later:

- A leaderboard. v0.1 is a measurement protocol, not a ranking product.
- A claim that any model "fails governance." The unit of measurement is
  **(model, runtime, governance-mode) → violation rate on the Layer 1
  fixtures**, not a verdict about the model in isolation.
- A general-purpose LLM evaluation framework. The track only measures what
  the frozen Layer 1 contract can adjudicate.

---

## 5. Evaluation matrix (v0.1)

The v0.1 matrix is intentionally narrow. Wider matrices are deferred until the
protocol has been run end-to-end at least once.

| Axis | v0.1 values |
|---|---|
| **Model** | One Claude model, one comparator model. Exact IDs pinned in the run manifest at execution time. |
| **Runtime** | (a) raw model API, (b) one agent-harness runtime in which Mneme already has an integration (Claude Code hook per Layer 1 §What Shipped). |
| **Governance mode** | `off` (no Mneme), `on` (Mneme `check_prompt` runs before generation, using the frozen retriever and enforcer). |
| **Scenario set** | The 7 shipped Layer 1 fixtures, unchanged. |
| **Repeats** | N ≥ 5 generations per (model, runtime, governance-mode, scenario) cell. N is pinned per run; N may not vary mid-run. |

Expanding the matrix beyond v0.1 (more models, more runtimes, more scenario
sets) is a v0.2 question and requires this plan to be revisited.

---

## 6. Metrics

All metrics are computed **per cell** = (model, runtime, governance-mode,
scenario), then aggregated. None of these metrics modify or replace the
Layer 1 metrics in the freeze document.

### 6.1 Primary metrics

| Metric | Definition | Why it matters |
|---|---|---|
| `ungoverned_drift_rate` | Fraction of `governance=off` generations whose Layer 2 verdict is `FAIL` on the Layer 1 contract. | Baseline drift on this model/runtime against this fixture set. |
| `governed_block_rate` | Fraction of `governance=on` runs in which Mneme `check_prompt` returns `FAIL` and blocks the generation before the model is called. | Whether governance fired at the prompt boundary. |
| `drift_reduction_rate` | `ungoverned_drift_rate − post_governance_violation_rate`, where `post_governance_violation_rate` is the fraction of `governance=on` cell runs that **still** end in a `FAIL` verdict despite Mneme having been consulted. | Headline citable metric: how much real drift the governance layer removes for this (model, runtime). |
| `violation_category_rate` | Per Layer 1 category (architecture / scope / anti-pattern / retrieval), the fraction of cell runs ending in `FAIL`. | Surfaces where a given (model, runtime) drifts most. |

### 6.2 Secondary / diagnostic metrics

| Metric | Definition | Role |
|---|---|---|
| `runtime_variance` | Spread of `ungoverned_drift_rate` and `drift_reduction_rate` across runtimes for the same model. | Tells us whether drift is a model property or a runtime property. |
| `repeatability` | For each cell, the share of repeats that produced the same Layer 2 verdict. | Sanity check: a cell with low repeatability cannot support a strong claim either way. |
| `weak_retrieval_rate` | Share of `governance=on` runs whose verdict is `WEAK_RETRIEVAL` (clean output, but the expected decision was never retrieved). | Layer 1 already exposes this; tracked here so cross-model results do not silently mask retrieval failures. |
| `block_then_fail_rate` | Share of `governance=on` runs where Mneme blocked, the model was re-prompted (if applicable), and the re-prompt still produced a `FAIL`. | Catches cases where governance fires but the model still drifts on a follow-up turn. |

### 6.3 Metrics explicitly NOT included in v0.1

- Code-quality scores. Layer 1 does not score quality; v0.1 inherits that.
- Token cost, latency, or any performance number. Not a governance signal.
- Subjective rater preference. v0.1 is mechanical; rater-based comparisons are
  a separate methodology with their own protocol.
- Anything derived by mutating `acceptable_decision_ids` (off-limits per
  Step 3C charter §5).

---

## 7. Repeatability and determinism

The Layer 1 benchmark is deterministic by construction (canned fixtures,
stable sort, no live model calls). This track introduces live model calls and
must therefore make its **non-determinism explicit** rather than pretending it
away.

Rules:

1. The Layer 1 benchmark itself remains canned. This track does **not** swap
   the canned fixtures for live calls. The live runner is a separate process
   that produces outputs the Layer 1 harness then adjudicates.
2. Every cell is run N ≥ 5 times. v0.1 pins N in the run manifest.
3. Temperature, top-p, system prompt template, and any agent-harness settings
   are recorded in the run manifest. A run that does not record these is not
   citable.
4. Model IDs are recorded as the provider-reported identifier at call time, not
   a marketing name.
5. The frozen Layer 1 retrieval and enforcement code path is the **only**
   adjudicator. No human override of a Layer 2 verdict is allowed inside a
   measurement run.
6. If a run cannot reproduce its own headline numbers within an agreed
   tolerance on a re-execution, the run is published as `unstable` and not
   used for cross-model comparison.

---

## 8. Reporting surface

### 8.1 Where results live

- Per-run artifacts (manifest, raw generations, Layer 2 verdicts, computed
  metrics) live under a new directory to be added in a later
  implementation PR (proposed: `examples/benchmarks/cross-model/<run-id>/`).
  No directory is created by this plan; the path is reserved.
- A human-readable summary lives alongside, similar in shape to
  `examples/benchmarks/reports/RESULTS.md`, but **separate from** the Layer 1
  RESULTS file. The Layer 1 RESULTS file is part of the freeze surface and is
  not edited by this track.

### 8.2 Versioning

- This track is versioned independently of Layer 1.
- v0.1 of the protocol corresponds to this plan. Behavioral changes to
  metrics, matrix, or determinism rules bump the protocol version.
- Layer 1's freeze version (v1.1) is recorded inside every cross-model run
  manifest so a reader can confirm which governance substrate was used.

### 8.3 What cannot be silently changed once published

- The metric definitions in §6.
- The matrix specification rules in §5.
- The determinism rules in §7.
- Any published `drift_reduction_rate` number for a given (model, runtime,
  protocol version) — corrections require a versioned re-publication, not an
  in-place edit.

---

## 9. Governance invariants for this track

These are non-negotiable. A measurement-track PR that violates any of them
must not merge.

1. **Layer 1 freeze is untouched.** No change to retrieval, enforcement,
   fixtures, K, scoring weights, metric formulas, verdict logic, or the
   `governed` aggregation filter.
2. **No `acceptable_decision_ids` mutation** to move any cross-model headline.
   Step 3C charter §5 applies in full.
3. **No new Layer 1 scenarios** added under cover of cross-model work. New
   scenarios still require the Step 3C anti-inflation criterion.
4. **No human override** of a Layer 2 verdict inside a measurement run.
5. **Run manifests are mandatory.** A run without a complete manifest (model
   IDs, runtime config, temperature, governance mode, N, Layer 1 freeze
   commit, protocol version) is not citable.
6. **GTM / pricing / customer / internal-strategy content stays out of this
   repo** (per `CLAUDE.md`). Cross-model results published here describe the
   measurement, not the business framing.
7. **`mneme check --mode warn`** remains clean against governance source on
   any PR landed under this track.

---

## 10. Phased delivery

v0.1 is a plan, not an implementation. The phasing below is the proposed
order; each phase is its own narrowly-scoped PR per repo policy.

### Phase A — Plan freeze (this PR)
- Land this document.
- No code, no fixtures, no result publication.
- Confirms the scope boundary against the Layer 1 freeze before any runner is
  built.

### Phase B — Run manifest + adjudication wiring (later PR)
- Define the run-manifest schema (JSON) and the location under
  `examples/benchmarks/cross-model/` once the directory is created.
- Wire a thin adjudication entry point that consumes raw generations and
  invokes the **existing**, frozen Layer 2 verdict logic. No new verdict
  logic is introduced.
- Tests: manifest schema validation, manifest-missing-field failure, frozen
  Layer 2 verdict parity against a captured generation.

### Phase C — First end-to-end run (later PR)
- Execute v0.1 matrix at N ≥ 5.
- Publish per-cell metrics and the run summary under
  `examples/benchmarks/cross-model/<run-id>/`.
- Update `docs/validation/governance-incident-log.md` with any
  retrieval-surprise or missed-drift observations surfaced by the run.

### Phase D — Cross-model report (later PR)
- A human-readable writeup that cites Phase C numbers, the Layer 1 freeze
  commit, and the protocol version. No headline number that is not
  reconstructible from Phase C artifacts is allowed.

Phases B–D each require this plan to be revisited if their scope drifts
beyond what §4 declares in-scope for v0.1.

---

## 11. Exit criteria for v0.1

v0.1 is complete when:

1. This plan is merged and referenced from the Layer 1 freeze's "Deferred
   Work" or roadmap surface as the cross-model track's anchor document.
2. A Phase C run has been executed under the matrix in §5, with a complete
   run manifest per §7.
3. `drift_reduction_rate` is reported per (model, runtime) cell, with
   `ungoverned_drift_rate`, `governed_block_rate`, and `repeatability`
   reported alongside — none of these in isolation.
4. The Phase D writeup explicitly states the Layer 1 freeze commit, the
   protocol version, the model IDs, the runtime configurations, and N.
5. No Layer 1 invariant from §9 was violated to produce any reported number.

Anything beyond this is v0.2.

---

## 12. Amendment procedure

This plan is the charter for the cross-model measurement track. To amend it:

1. Open a PR titled `[cross-model-measurement] <change>`.
2. Reference the specific section being amended.
3. State whether the amendment changes a metric definition (§6), the matrix
   (§5), the determinism rules (§7), or the governance invariants (§9).
   Amendments to §9 require an accompanying note in the Layer 1 freeze
   amendment trail confirming that no freeze invariant is being relaxed.
4. Do **not** amend this plan to retroactively justify a published number.
   Corrections are versioned re-publications under a new protocol version.
