# Decision memory vs RAG

Canonical article: https://mnemehq.com/insights/decision-memory-vs-rag/

## Why this note exists

RAG and decision memory solve different problems.

RAG helps a model retrieve relevant information from a corpus. Decision memory helps an engineering system preserve architectural intent and enforce project decisions across AI-assisted development workflows.

Mneme uses this distinction deliberately. Architectural governance needs deterministic constraints, sourceable decisions, and repeatable enforcement. It should not depend only on semantic similarity or whatever a model happens to retrieve in a long context window.

## The distinction

| Question | RAG | Decision memory |
|---|---|---|
| Primary job | Retrieve relevant context | Preserve and enforce architectural intent |
| Typical unit | Chunk, document, embedding result | Decision, constraint, ADR, anti-pattern |
| Failure mode | Missing or irrelevant retrieval | Architectural drift or unenforced decisions |
| Best surface | Q&A, search, synthesis | hooks, CI, agent context, review gates |
| Governance role | Informative | Constraining |

## Why vector search is not enough for architectural governance

Architectural decisions are not just facts to retrieve. They are constraints that should shape what an agent is allowed to generate.

For example, a repo decision might say:

```text
Do not import from MnemeHQ.memory_store.
Use mneme.memory_store instead.
```

A RAG system may retrieve that decision if the prompt is close enough. Mneme turns it into a governance rule that can be injected into agent context and checked deterministically before the change lands.

## Mneme's implementation direction

Mneme favors repo-native governance artifacts:

- ADRs
- `.mneme/project_memory.json`
- deterministic decision retrieval
- explicit anti-patterns
- hook and CI enforcement
- source-linked governance context

That makes the memory operational rather than merely informational.

## Practical rule

Use RAG when the agent needs to know more.

Use decision memory when the agent must not forget what the system has already decided.
