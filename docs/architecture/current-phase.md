# Mneme — Current Phase

> One-page orientation: where Mneme is right now, what is frozen, what is experimental, what is deferred.
> If you are a contributor, design partner, or new reader, start here.

## Phase

**Layer 1 — validation phase.**

Layer 1 is local-repo, single-developer, project-scoped architectural governance for AI-assisted code generation. The mechanism is frozen; what remains is real-world validation.

## What is frozen

Pinned at commit [`e73ff7d`](https://github.com/TheoV823/mneme/commit/e73ff7d) and documented in [layer1-freeze-e73ff7d.md](./layer1-freeze-e73ff7d.md):

- **Retrieval mechanics** — deterministic bag-of-tokens scoring with fixed weights, stopword floor, insertion-order tiebreak.
- **Enforcement semantics** — `anti_patterns` → FAIL, `"no X"` constraints → WARN, top-K-only, word-boundary matching.
- **Benchmark methodology** — two-layer scoring (retrieval vs. enforcement), structured-fixture path with TXT fallback, five-verdict semantics, K=3 canonical.
- **Charter principles** — deterministic > clever, auditable > autonomous, prevention before review, no passive ingestion, no auto-learning, no hidden vector magic.
- **Scope wedge** — local-repo, single-developer, project-scoped. Multi-repo / team / org sync is Layer 2.

No behavioral change to retrieval or enforcement is in scope without an explicit charter amendment.

## What is experimental

These are shipped but not under freeze; they may evolve without a charter amendment:

- Cursor rules export.
- Claude Code hook integration.
- ADR parser/compiler/validator pipeline.
- The `POST /complete` minimal API surface (no auth, no persistence).
- Site-level benchmark presentation copy.

## What is deferred

Layer 2 territory. Listed in the freeze doc under §Deferred Work. Promoting any of these requires Layer 1 exit criteria to be met first:

- ADR lineage and versioning.
- Multi-developer / team governance.
- Shared policy packs.
- MCP / API surface beyond the minimal `POST /complete`.
- Deeper IDE integrations (LSP, JetBrains).
- CI enforcement evolution.
- Policy compiler / higher-level DSL.
- Cross-repo / org-wide governance.

The freeze doc also lists "Intentionally NOT Solved" items — those are not deferred, they are out of scope for Mneme as a project.

## What success means right now

The Layer 1 exit criteria from the freeze doc:

1. Benchmark integrity stabilized — **met** at `e73ff7d`.
2. Deterministic enforcement validated — **met** at `e73ff7d`.
3. Real-world drift prevention demonstrated — **open**, requires external evidence.
4. Design-partner validation complete — **open**.
5. Governance wedge validated — **open**.

Items 1 and 2 are mechanical. Items 3, 4, and 5 are the work of this validation phase. They cannot be completed by writing more code in this repo.

## Links

- **Freeze artifact** — [layer1-freeze-e73ff7d.md](./layer1-freeze-e73ff7d.md)
- **Governance representation** — [governance-representation.md](./governance-representation.md) — how ADRs become deterministic enforcement rules
- **Benchmark methodology (public)** — [/benchmark/](https://mnemehq.com/benchmark/) and [/docs/benchmark-methodology/](https://mnemehq.com/docs/benchmark-methodology/)
- **Roadmap** — [docs/roadmap/](../roadmap/)
- **ADRs** — [docs/adr/](../adr/)
- **Repo governance source of truth** — [`.mneme/project_memory.json`](../../.mneme/project_memory.json)

## Contributor guidance

Before opening a PR, ask: does this change behavior in `decision_retriever.py`, `enforcer.py`, `benchmark.py`, or any benchmark fixture? If yes, it is a charter-level change and the freeze doc's amendment procedure applies. If no — docs, tooling, integrations, site, examples — proceed normally with `[memory]` prefix discipline for `project_memory.json` edits.
