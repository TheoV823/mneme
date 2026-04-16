# mneme-project-memory

**Mneme injects project memory into AI calls so outputs follow your decisions.**

---

## The problem

You ask an LLM to help with your project. It suggests Postgres when you committed to JSON files. It recommends langchain when you explicitly banned it. It proposes rebuilding a module you decided to extend. Every call starts from zero because the model has no memory of your project's constraints, architecture decisions, or established patterns.

The usual fix is prompt engineering -- manually pasting context into every call. That does not scale, is not auditable, and drifts the moment anyone forgets to update the preamble.

## What Mneme is

**Mneme** is a portable project memory and evaluation nucleus for AI workflows.

This repository demonstrates the first core capability: injecting structured project memory into LLM/API calls so outputs stay consistent with prior project decisions.

```python
from mneme.memory_store import MemoryStore
from mneme.retriever import Retriever
from mneme.context_builder import format_context_packet
from mneme.llm_adapter import LLMAdapter

memory = MemoryStore("examples/project_memory.json").load()
packet = Retriever(memory).retrieve("Should we rebuild from scratch?")
response = LLMAdapter().complete(
    user="Should we rebuild from scratch?",
    system=format_context_packet(packet),
)
print(response.content)
```

## The flagship example

**Task**: "Should we rebuild the retrieval system from scratch with embeddings?"

**WITHOUT MNEME:**
```
We could consider rebuilding the system with a vector database and embedding
model. This would improve semantic matching and scale better long-term.
Sentence-transformers is a good option for generating embeddings...
```

**WITH MNEME:**
```
Do not rebuild from scratch. The project has an explicit rule to extend current
infrastructure before rebuilding (rule-001). Keyword scoring was chosen
intentionally -- it is deterministic, has no ML dependencies, and is easy to
debug. The team already declined adding sentence-transformers in v1. Extend
the current retriever instead.
```

**MNEME ALIGNMENT:**
```
  [OK]   rule-001: Extend current infrastructure before rebuilding
  [OK]   rule-002: Keep v1 retrieval deterministic
  [OK]   anti-001: Do not use langchain
  [OK]   dec-001: Declined. Kept keyword scoring.
  alignment_score: 1.00
```

Same model. Same question. Different answer -- because it has the project's actual decisions.

## What this repo demonstrates

A five-stage pipeline that runs locally in under two minutes:

```
project_memory.json -> MemoryStore -> Retriever -> ContextBuilder -> LLMAdapter -> Evaluator
```

1. **Load** structured project memory from a human-editable JSON file
2. **Retrieve** the rules and examples relevant to the current task
3. **Build** a context packet and inject it into the system prompt
4. **Call** the LLM (or dry-run without an API key)
5. **Evaluate** whether the response followed your rules

The demo runs each task twice -- once without memory (baseline) and once with memory injected -- so you can see the delta.

## Why not just RAG?

RAG retrieves **information**. Mneme retrieves **decisions**.

* Not retrieval of documents — retrieval of **decisions your project already made**
* Not long context — a **structured context packet** with only what is relevant to the query
* Not autonomy — **consistency enforcement**: the model is told what was decided, not asked to figure it out

| | RAG | Mneme |
|---|---|---|
| Input | Documents, chunks, embeddings | Rules, constraints, decision records |
| Goal | Inform the response | Shape the response |
| Output effect | Model knows more | Model follows your decisions |
| Evaluation | "Did it use the right source?" | "Did it respect the constraint?" |

Mneme is not a search engine for your docs. It is a structured rule system that tells the model what your project has already decided and checks whether it listened.

## Architecture

```
mneme-project-memory/
  mneme/
    schemas.py          Dataclasses: MemoryItem, DecisionExample, ContextPacket
    memory_store.py     Load project_memory.json into typed Python objects
    retriever.py        Score items by keyword overlap + tag match + priority weight
    context_builder.py  Format a ContextPacket into a system prompt string
    llm_adapter.py      Thin Anthropic API wrapper with dry-run mode
    evaluator.py        Deterministic alignment checker (rule + decision checks)
  examples/
    project_memory.json 20 memory items + 5 decision examples for this repo
    demo_tasks.json     3 decision-oriented tasks for the before/after demo
  demo.py               CLI runner: baseline vs. Mneme-enhanced, with alignment scoring
```

### Memory item types

| Type | What it is | Evaluator behavior |
|------|-----------|-------------------|
| `rule` | Hard constraint -- must follow | Violation flagged |
| `anti_pattern` | Explicitly ruled out | Violation flagged |
| `preference` | Should-follow guideline | Surfaced in context |
| `fact` | Established truth (language, version, provider) | Surfaced in context |
| `architecture_decision` | ADR-style choice with rationale | Surfaced in context |
| `example` | Worked illustration or code snippet | Surfaced in context |

### Decision examples

Separate from items. Each one records a situation, what the project decided, and why:

```json
{
  "task": "A contributor proposed adding sentence-transformers for semantic retrieval in v1.",
  "decision": "Declined. Kept keyword scoring.",
  "rationale": "Heavy ML dependency that breaks the pip-install-in-30-seconds contract."
}
```

These are injected as prior decisions so the model learns how your project reasons, not just what it decided.

### Retrieval

Fully deterministic. Same query + same memory file = same output every time.

- **Keyword overlap**: +1.0 per query token found in item title/content
- **Tag match**: +1.5 per query token that exactly matches a tag
- **Priority scaling**: score multiplied by item weight (high=1.5, medium=1.0, low=0.5)
- **Rules always surface**: rules and anti-patterns are included regardless of query relevance
- **Fallback**: if no facts match, top 3 by weight are included so context is never empty

No embeddings. No vector store. Determinism is a feature, not a limitation.

### Evaluation

The evaluator checks the response against the rules that were actually injected (the `ContextPacket`), not the full memory file. Two checks:

1. **Rule check**: extracts forbidden terms from each rule/anti-pattern. A violation fires when a term appears with a positive recommendation signal and no negation nearby.
2. **Decision check**: for past decisions where the project said "no," checks whether the response recommends the declined subject anyway.

Score = fraction of checks passed. 1.00 = no violations detected.

The evaluator is deterministic, fast, and auditable. The upgrade path to a model-based judge is explicit in the code: replace two functions, keep everything else.

## Quickstart

```bash
git clone https://github.com/mneme-project/mneme-project-memory
cd mneme-project-memory

# Core only
pip install -e .

# Core + API layer
pip install -e ".[api]"
```

```bash
# Set your Anthropic API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...
```

```bash
# Run the before/after demo (live API calls)
python demo.py

# Run without an API key (prints prompts, no API calls)
python demo.py --dry-run

# Run a single task
python demo.py --task task-001

# Inspect what Mneme would inject, without calling the LLM
python demo.py --context-only
```

### Requirements

- Python 3.11+
- `anthropic` >= 0.25.0
- `python-dotenv` >= 1.0.0

That is the entire dependency list.

## Example: project_memory.json

The included example describes this repo itself. Abbreviated:

```json
{
  "meta": {
    "name": "mneme-context-engine",
    "description": "Inject structured project memory into LLM API calls.",
    "version": "0.1.0"
  },
  "items": [
    {
      "id": "rule-001",
      "type": "rule",
      "title": "Extend current infrastructure before rebuilding",
      "content": "When adding capability, first ask whether an existing module can be extended.",
      "tags": ["architecture", "scope"],
      "priority": "high"
    },
    {
      "id": "anti-001",
      "type": "anti_pattern",
      "title": "Do not use langchain",
      "content": "langchain abstracts away the API surface this library is designed to control.",
      "tags": ["langchain", "forbidden"],
      "priority": "high"
    }
  ],
  "examples": [
    {
      "task": "A contributor proposed adding sentence-transformers for semantic retrieval in v1.",
      "decision": "Declined. Kept keyword scoring.",
      "rationale": "Heavy ML dependency. Breaks pip-install-in-30-seconds contract."
    }
  ]
}
```

The full file has 20 items and 5 decision examples. Edit it for your own project -- it is plain JSON, no tooling required.

## Demo tasks

| Task | What Mneme catches |
|------|--------------------|
| Rebuild from scratch? | rule-001 (extend over rebuild), dec-001 (embeddings declined) |
| Broaden v1 scope? | anti-002 (no agentic loops), rule-004 (narrow MVP) |
| Mix project + personal memory? | rule-003 (separate project from personal), dec-002 (per-project only) |

## Why this matters

- **LLM calls are stateless.** Every API call starts from zero. Without explicit project context, the model gives plausible answers that routinely contradict your established decisions. Mneme makes the context explicit and the injection automatic.

- **Project memory is a structured artifact, not a blob.** Dumping raw notes into a system prompt does not scale. Mneme types each piece of memory (rule, anti-pattern, decision example), assigns priority, and retrieves only what is relevant. The context stays compact.

- **Evaluation closes the loop.** Injecting context is half the problem. The other half is knowing whether it worked. The evaluator checks the response against the rules that were injected and returns a score. This is the beginning of measurable LLM alignment at the project level.

## Roadmap

| Version | Capability |
|---------|-----------|
| **v0.1** (this repo) | JSON-backed memory, keyword retrieval, deterministic evaluation, before/after demo |
| **v0.2** | Embedding-based retrieval (opt-in), CLI tooling for memory management |
| **v0.3** | LLM-judge evaluator mode, positive-alignment verification |
| **v1.0** | Multi-project support, memory versioning, CI integration for alignment checks |
| **Beyond** | Learned retrieval ranking, cross-project memory, agent-level memory management |

## Use Mneme via API

Mneme now includes a minimal API layer so other workflows can call it directly.

### Endpoint

`POST /complete`

### What it does

The endpoint accepts:

* a `question`
* a project memory input, either as:

  * an inline JSON object, or
  * a path to a local JSON file

Mneme then:

1. loads the memory
2. retrieves relevant rules, facts, and examples
3. builds a compact context packet
4. injects that context into the LLM call
5. returns the answer plus a summary of what context was used

### Run locally

```bash
# Install with API extras
pip install -e ".[api]"

uvicorn app.api:app --reload
```

### Request shape

```json
{
  "question": "Should we rebuild from scratch?",
  "memory": "examples/project_memory.json"
}
```

You can also pass memory inline:

```json
{
  "question": "Should we broaden scope in v1?",
  "memory": {
    "meta": {
      "name": "mneme",
      "description": "Portable project memory and evaluation nucleus for AI workflows."
    },
    "items": [
      {
        "id": "rule-001",
        "type": "rule",
        "title": "Extend before rebuild",
        "content": "Prefer extending existing infrastructure over rebuilding from scratch in v1.",
        "tags": ["architecture", "mvp"],
        "priority": "high"
      }
    ],
    "examples": []
  }
}
```

### Example with curl

```bash
curl -X POST http://127.0.0.1:8000/complete \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Should we rebuild from scratch?",
    "memory": "examples/project_memory.json"
  }'
```

### Example response

```json
{
  "answer": "No. Extend the current system rather than rebuilding it. Prior project rules favor reuse, narrow scope, and deterministic iteration in v1.",
  "context_summary": {
    "rules": 3,
    "constraints": 2,
    "facts": 4,
    "examples": 2
  }
}
```

### Context summary fields

* `rules` — hard project rules injected into the call
* `constraints` — anti-patterns, boundaries, and soft preferences
* `facts` — relevant project facts and architecture decisions
* `examples` — prior decision examples included in context

### Why this matters

This is the first API surface for Mneme.

It turns Mneme from a local demo into a callable decision-consistency layer that can sit between an external workflow and an LLM. A pipeline can now send a question plus project memory and get back an answer shaped by prior project decisions rather than generic model behavior.

### Current scope

This API is intentionally minimal:

* no auth
* no database
* no persistence layer
* no multi-project serving

It exists to prove the core Mneme loop in the simplest usable form:
**project memory → retrieval → context injection → answer**

---

## Status

This is the first public module of **Mneme**. It is a narrow, intentional wedge: one capability, demonstrated clearly, with a clean upgrade path.

Mneme is a portable project memory and evaluation nucleus for AI workflows. This repo is where it starts.

## License

MIT
