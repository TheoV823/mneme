"""
pipeline.py — End-to-end Mneme pipeline.

Flow:
    MemoryStore  ->  DecisionRetriever  ->  format_decisions (top N)
                     ->  LLMAdapter  ->  ConflictDetector

``Pipeline.run(query)`` returns a ``PipelineResult`` bundling everything
observable: scored decisions, which were injected, the system prompt
that was sent, the LLM response, and any conflicts detected.

This is a parallel v2 pipeline. The legacy Retriever + ContextBuilder +
Evaluator path in demo.py is unchanged and continues to work independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mneme.conflict_detector import Conflict, ConflictDetector
from mneme.context_builder import DEFAULT_MAX_DECISIONS, format_decisions
from mneme.decision_retriever import DecisionRetriever, ScoredDecision
from mneme.llm_adapter import LLMAdapter
from mneme.memory_store import MemoryStore
from mneme.schemas import Decision, LLMResponse


@dataclass
class PipelineResult:
    """Observable output of a pipeline run — designed for debug + display.

    Attributes:
        query:               Original user query.
        scored:              All decisions ranked for this query.
        injected_decisions:  The top-N decisions actually injected.
        system_prompt:       The formatted prompt sent to the LLM.
        response:            The LLM response (or dry-run stub).
        conflicts:           Conflicts detected in the response.
    """

    query: str
    scored: list[ScoredDecision]
    injected_decisions: list[Decision]
    system_prompt: str
    response: LLMResponse
    conflicts: list[Conflict] = field(default_factory=list)


class Pipeline:
    """Composes MemoryStore + DecisionRetriever + ContextBuilder + LLMAdapter + ConflictDetector.

    Args:
        memory_path:   Path to project_memory.json.
        dry_run:       Pass-through to LLMAdapter; if True, no API call.
        max_decisions: Top-N cap on decisions injected per call.
    """

    def __init__(
        self,
        memory_path: str | Path,
        dry_run: bool = False,
        max_decisions: int = DEFAULT_MAX_DECISIONS,
    ) -> None:
        self.store = MemoryStore(memory_path)
        self.store.load()
        self.retriever = DecisionRetriever(self.store.decisions())
        self.adapter = LLMAdapter(dry_run=dry_run)
        self.detector = ConflictDetector()
        self.max_decisions = max_decisions

    def run(
        self,
        query: str,
        _override_response: str | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline for one query.

        Args:
            query:              The user task/question.
            _override_response: Test hook — force a specific response string
                                to exercise conflict detection paths.

        Returns:
            A PipelineResult with every stage's output recorded.
        """
        scored = self.retriever.retrieve(query)
        system_prompt = format_decisions(scored, max_items=self.max_decisions)

        injected: list[Decision] = []
        seen: set[str] = set()
        for s in scored:
            if s.score <= 0:
                continue
            if s.decision.id in seen:
                continue
            seen.add(s.decision.id)
            injected.append(s.decision)
            if len(injected) >= self.max_decisions:
                break

        if _override_response is not None:
            response = LLMResponse(
                content=_override_response,
                model="test-override",
                usage={"input": 0, "output": 0},
            )
        else:
            response = self.adapter.complete(
                user=query, system=system_prompt or None
            )

        conflicts = self.detector.detect(response.content, injected)

        return PipelineResult(
            query=query,
            scored=scored,
            injected_decisions=injected,
            system_prompt=system_prompt,
            response=response,
            conflicts=conflicts,
        )
