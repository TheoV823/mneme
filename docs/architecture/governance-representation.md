# Governance Representation

> How Mneme turns human-authored architectural decisions into deterministic enforcement rules.

---

## Human-readable decisions

Architectural decisions live where humans write and review them: Architecture Decision Records (ADRs) under `docs/adr/`, and structured entries in `.mneme/project_memory.json`.

ADRs are prose. They describe context, rationale, trade-offs, and alternatives. They are readable by any engineer without tooling. Their value is communication and historical record.

But prose alone cannot be enforced. An LLM does not reliably recall that ADR-006 disallows a certain pattern three weeks after it was written. ADR text is not evaluated at prompt time. It is not consistently retrieved. It does not produce a verdict.

Mneme's job is to bridge that gap.

---

## Structured governance representation

The governance source of truth is `.mneme/project_memory.json`. Each Decision in that file has a typed, structured schema:

```json
{
  "id": "anti-vector-langchain-agents",
  "type": "anti_pattern",
  "title": "No vector DB, no agent loops, no litellm - Anthropic SDK only",
  "content": "...",
  "tags": ["retrieval", "embeddings", "vector-db", "anthropic", "v1-scope"],
  "priority": "high"
}
```

Decisions also carry `constraints`, `anti_patterns`, `scope`, `rationale`, and `decision` fields — each with different retrieval weight and enforcement semantics.

This structure is what makes enforcement possible. The retriever scores against these fields independently. The enforcer evaluates `anti_patterns` and `constraints` against the prompt. The conflict detector reasons across multiple decisions. None of that is feasible against free-form prose.

The ADR-to-memory pipeline (`adr_parser.py`, `adr_validator.py`, `adr_compiler.py`) exists to keep these two representations in sync: ADRs remain the human artifact; `.mneme/project_memory.json` is the enforcement artifact.

---

## Why deterministic enforcement matters

Two engineers running the same memory against the same prompt must see the same verdict. A CI step running on a Tuesday must produce the same result as the one running on a Friday. A benchmark must be byte-reproducible across environments.

These requirements rule out probabilistic or learned retrieval for the enforcement surface.

Mneme's retrieval is bag-of-tokens scoring with documented, fixed weights (`scope`=2.0, `constraints`=1.5, `anti_patterns`=1.5, `decision`=1.0, `rationale`=0.5), a stopword floor, and an insertion-order tiebreak. Given a fixed memory and a fixed query, the same decisions surface in the same order every time.

Enforcement follows the same discipline. `anti_patterns` matches produce a `FAIL`. `"no X"` constraints produce a `WARN`. Word-boundary matching, top-K-only, no fuzzy scoring.

This is not a simplification imposed by the early stage of the project. It is a deliberate charter principle: **deterministic > clever**. A retriever that gives the same answer twice is preferred to one that gives a slightly better answer unpredictably. The enforcement contract is only useful if it is stable.

---

## Example transformation

**ADR-authored intent:**
> "Do not introduce a vector database, embeddings, semantic search, agentic tool-use loops, or provider-abstraction layers like litellm. The only LLM provider is Anthropic via the official `anthropic` SDK."

**Structured governance representation:**
```json
{
  "id": "anti-vector-langchain-agents",
  "type": "anti_pattern",
  "anti_patterns": ["vector-db", "embeddings", "litellm", "langchain", "agent loops"],
  "constraints": ["no second LLM provider", "no litellm", "anthropic SDK only"],
  "priority": "high"
}
```

**Enforcement outcome:** a prompt containing "use litellm for model abstraction" matches the `anti_pattern` content → `FAIL`, severity 2, blocked before generation.

**What is recorded:** which decision matched, which field triggered, which term in the prompt fired the rule, what the retrieval score was, and why this decision was in the top-3.

Every verdict is reconstructible. A human can follow the chain from the input prompt to the matched decision to the rule text that fired. There is no inference step, no black-box scoring, no hidden weight that cannot be audited.

---

## The ADR pipeline

Three modules connect ADRs to the enforcement layer:

- **`adr_parser.py`** — reads `docs/adr/*.md`, extracts structured fields from the Markdown schema.
- **`adr_validator.py`** — checks that ADR decisions reference valid IDs in `project_memory.json`; surfaces divergence.
- **`adr_compiler.py`** — reconciles ADR-derived fields against live memory entries.

The pipeline is experimental (see [current-phase.md](./current-phase.md)). It is not a CI gate today; it is a reconciliation tool. The authoritative enforcement memory is always `.mneme/project_memory.json` as edited and reviewed under the `[memory]` PR convention.

---

## Future direction

The structured representation in `project_memory.json` is the foundation for future governance work. Potential directions include:

- **Richer constraint grammar.** The current enforcer recognises `"no X"` constraints. Expressing `"always use X"` or `"require X before Y"` requires a constraint grammar extension.
- **ADR lineage.** Supersession chains, decision provenance, amendment history as first-class fields.
- **Shared policy packs.** Pre-authored decision sets for common patterns (e.g. a "Python service" baseline) distributed and composed into project memory.
- **Cross-repo governance.** Memory distributed beyond a single `.mneme/` directory, with a remote sync layer.

These are Layer 2 territory. None of them are in scope until the Layer 1 wedge — local-repo, single-developer, deterministic enforcement — is validated in the real world.

---

## Related

- [current-phase.md](./current-phase.md) — phase status, what is frozen, what is experimental.
- [layer1-freeze-e73ff7d.md](./layer1-freeze-e73ff7d.md) — full freeze artifact: charter principles, benchmark methodology, known limitations.
- [docs/adr/](../adr/) — human-authored decision records.
- [`.mneme/project_memory.json`](../../.mneme/project_memory.json) — enforcement source of truth.
