# mneme/adr_import.py
"""
adr_import.py — Import flow for ADR corpora.

Composition module that wires together the existing parser, validator, and
precedence resolver, then adds (a) a graph projection, (b) conflict
detection against a target memory file, (c) preview formatting, and
(d) atomic persistence. Each helper is independent and pure; the CLI
subcommand orchestrates them.

Pipeline modules (MemoryStore, DecisionRetriever, ContextBuilder,
LLMAdapter, Evaluator) are NOT imported here per .mneme/project_memory.json
rule-pipeline-modules. Persistence happens by writing the JSON file
directly; consumers re-load it via MemoryStore.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mneme.adr_schema import ADR


GraphStatus = Literal["active", "superseded", "deprecated", "inactive"]


@dataclass(frozen=True)
class DecisionNode:
    """User-facing minimal graph projection of one ADR."""

    id: str
    status: GraphStatus
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str | None = None


def project_decision_graph(adrs: list[ADR]) -> list[DecisionNode]:
    """Project a parsed ADR corpus into the minimal graph.

    Status mapping:
      ADR.status == "accepted" AND not in any other ADR's supersedes -> "active"
      ADR.status == "accepted" AND IS in some other ADR's supersedes -> "superseded"
      ADR.status == "superseded" (explicit in frontmatter)            -> "superseded"
      ADR.status == "deprecated"                                       -> "deprecated"
      ADR.status == "proposed"                                         -> "inactive"

    ``superseded_by`` is the id of the ADR that explicitly supersedes
    this one, or None. If multiple ADRs claim to supersede the same
    target, the lexicographically lowest id wins (deterministic; rare
    in practice and validate_corpus catches the cycle case).
    """
    superseded_by_map: dict[str, str] = {}
    for a in adrs:
        for ref in a.supersedes:
            existing = superseded_by_map.get(ref)
            if existing is None or a.id < existing:
                superseded_by_map[ref] = a.id

    out: list[DecisionNode] = []
    for a in adrs:
        if a.status == "deprecated":
            status: GraphStatus = "deprecated"
        elif a.status == "superseded":
            status = "superseded"
        elif a.status == "proposed":
            status = "inactive"
        elif a.status == "accepted":
            status = "superseded" if a.id in superseded_by_map else "active"
        else:
            status = "inactive"

        out.append(DecisionNode(
            id=a.id,
            status=status,
            supersedes=list(a.supersedes),
            superseded_by=superseded_by_map.get(a.id),
        ))
    return out


__all__ = ["DecisionNode", "GraphStatus", "project_decision_graph"]
