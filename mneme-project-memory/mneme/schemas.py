"""
schemas.py — Core data models for Mneme project memory.

All models are plain dataclasses. No database, no ORM.
The memory store deserialises these from a JSON file at load time.

Memory item types
-----------------
fact                 A concrete, established truth about the project
                     (language, version, repo name, etc.).
rule                 A must-follow constraint — violation should be flagged
                     by the evaluator.
preference           A should-follow guideline. Not a hard error if skipped,
                     but should surface in context.
architecture_decision
                     A recorded ADR-style choice: what was decided and why.
                     Useful for preventing revisits.
anti_pattern         Something explicitly ruled out. Evaluator checks that
                     the LLM response does not suggest it.
example              A worked illustration — a snippet, a file, a pattern.
                     Injected as a concrete reference.

Priority levels
---------------
high    → surfaces first in retrieval; weight multiplier 1.5
medium  → default; weight multiplier 1.0
low     → background context; weight multiplier 0.5
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ── Type aliases ─────────────────────────────────────────────────────────────

MemoryItemType = Literal[
    "fact",
    "rule",
    "preference",
    "architecture_decision",
    "anti_pattern",
    "example",
]

Priority = Literal["high", "medium", "low"]

PRIORITY_WEIGHT: dict[str, float] = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.5,
}


# ── Core models ───────────────────────────────────────────────────────────────

@dataclass
class ProjectMeta:
    """Project-level metadata injected into every context block.

    Attributes:
        name:        Short project identifier, e.g. "mneme-context-engine".
        description: One-sentence summary of the project's purpose.
        version:     Current version string.
        owner:       Team or person responsible for this memory file.
        created:     ISO 8601 date when the memory file was initialised.
    """

    name: str
    description: str
    version: str = "0.1.0"
    owner: str = ""
    created: str = ""


@dataclass
class MemoryItem:
    """A single structured piece of project memory.

    Each item represents one fact, rule, preference, decision,
    anti-pattern, or example that should inform LLM outputs.

    Attributes:
        id:       Unique identifier within the project, e.g. "rule-001".
        type:     One of the MemoryItemType literals (see module docstring).
        title:    Short human-readable label for this item.
        content:  The full text injected into context. Write this as if
                  briefing a developer who is new to the project.
        tags:     Free-form keywords for retrieval matching.
        priority: Retrieval weight tier — "high", "medium", or "low".
    """

    id: str
    type: MemoryItemType
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    priority: Priority = "medium"

    @property
    def weight(self) -> float:
        """Numeric weight derived from priority, used by the retriever."""
        return PRIORITY_WEIGHT.get(self.priority, 1.0)


@dataclass
class DecisionExample:
    """A recorded project decision with task context and rationale.

    Decision examples teach the model *how* this project reasons, not
    just *what* it has decided. They are injected as few-shot context.

    Attributes:
        id:        Unique identifier, e.g. "ex-001".
        task:      The situation or question that prompted the decision.
        decision:  What was chosen or done.
        rationale: Why — the reasoning that future calls should follow.
        tags:      Free-form keywords for retrieval matching.
    """

    id: str
    task: str
    decision: str
    rationale: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ProjectMemory:
    """The full memory store for one project.

    Attributes:
        meta:     Project-level metadata (name, description, version).
        items:    All MemoryItem entries — facts, rules, preferences, etc.
        examples: All DecisionExample entries showing past reasoning.
    """

    meta: ProjectMeta
    items: list[MemoryItem] = field(default_factory=list)
    examples: list[DecisionExample] = field(default_factory=list)


# ── Pipeline models ───────────────────────────────────────────────────────────

@dataclass
class ContextPacket:
    """Structured context assembled from retrieved project memory.

    This is the output of ``Retriever.retrieve()`` and the input to
    ``ContextBuilder.format()``. It separates memory into named sections
    so the context builder can render each one appropriately and so callers
    can inspect individual sections without parsing prompt text.

    Attributes:
        project_summary:   One-line project description for the preamble.
        hard_constraints:  Rules and anti-patterns — always injected,
                           regardless of query relevance.
        preferred_patterns: Preferences that scored above zero for this query.
        relevant_facts:    Facts, architecture decisions, and examples that
                           scored above zero for this query.
        decision_examples: Past decisions ranked by relevance to the query.
        output_guidance:   Closing instruction appended to every prompt.
        query:             The original query that generated this packet.
    """

    project_summary: str
    hard_constraints: list[MemoryItem]
    preferred_patterns: list[MemoryItem]
    relevant_facts: list[MemoryItem]
    decision_examples: list[DecisionExample]
    output_guidance: str
    query: str


@dataclass
class LLMResponse:
    """A response from an LLM adapter call.

    Attributes:
        content: The raw text returned by the model.
        model:   Model identifier used for the call.
        usage:   Token counts keyed by "input" and "output".
    """

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AlignmentResult:
    """Outcome of evaluating an LLM response against an injected ContextPacket.

    The evaluator checks the response against every hard constraint and
    injected decision example, then classifies each as matched or missed.
    "Matched" means no violation was detected — not that the response
    explicitly confirmed the rule. This is intentional: deterministic
    evaluation can reliably detect violations; positive alignment
    verification requires an LLM judge (a planned v2 capability).

    Attributes:
        alignment_score: Fraction of checks passed (0.0 to 1.0).
                         1.0 means no violations detected.
                         0.0 means every check failed.
        matched_rules:   Human-readable labels of checks that passed.
        missed_rules:    Human-readable labels of checks that failed,
                         each including a brief reason.
        explanation:     2-3 sentence plain English summary of the result.
    """

    alignment_score: float
    matched_rules: list[str]
    missed_rules: list[str]
    explanation: str
