"""
decision_retriever.py — Score Decision records against a query.

Scoring formula (deterministic, no external libraries):

    score =
        overlap(query, decision)      * 1.0
      + overlap(query, scope)         * 2.0
      + overlap(query, constraints)   * 1.5
      + overlap(query, anti_patterns) * 1.5
      + overlap(query, rationale)     * 0.5

A ``ScoredDecision`` bundles the decision with its score and a per-field
match count so callers can show *why* a decision matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from mneme.schemas import Decision


_WEIGHTS: dict[str, float] = {
    "decision": 1.0,
    "scope": 2.0,
    "constraints": 1.5,
    "anti_patterns": 1.5,
    "rationale": 0.5,
}


def _tokenize(text: str) -> set[str]:
    """Lowercase tokens of length >= 3."""
    return {w for w in re.split(r"\W+", text.lower()) if len(w) >= 3}


def _tokenize_list(values: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for v in values:
        tokens |= _tokenize(v)
    return tokens


@dataclass
class ScoredDecision:
    """A Decision paired with its relevance score and per-field match counts.

    Attributes:
        decision: The Decision being scored.
        score:    Total weighted score (>= 0).
        matches:  Per-field raw token match counts, e.g.
                  {"decision": 1, "scope": 2, "constraints": 0, ...}.
    """

    decision: Decision
    score: float
    matches: dict[str, int] = field(default_factory=dict)


class DecisionRetriever:
    """Scores a list of Decisions against a free-text query.

    Args:
        decisions: List of Decision records to score.
    """

    def __init__(self, decisions: list[Decision]) -> None:
        self.decisions = list(decisions)

    def retrieve(self, query: str) -> list[ScoredDecision]:
        """Return all decisions, scored and sorted descending by score."""
        query_tokens = _tokenize(query)
        scored = [self._score(d, query_tokens) for d in self.decisions]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def _score(self, d: Decision, query_tokens: set[str]) -> ScoredDecision:
        fields: dict[str, set[str]] = {
            "decision": _tokenize(d.decision),
            "scope": _tokenize_list(d.scope),
            "constraints": _tokenize_list(d.constraints),
            "anti_patterns": _tokenize_list(d.anti_patterns),
            "rationale": _tokenize(d.rationale),
        }
        matches = {name: len(query_tokens & toks) for name, toks in fields.items()}
        score = sum(matches[name] * _WEIGHTS[name] for name in _WEIGHTS)
        return ScoredDecision(decision=d, score=score, matches=matches)
