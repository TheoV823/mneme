"""Top-N decision injection in ContextBuilder."""
from mneme.context_builder import format_decisions, DEFAULT_MAX_DECISIONS
from mneme.decision_retriever import ScoredDecision
from mneme.schemas import Decision


def _scored(decision_id: str, score: float) -> ScoredDecision:
    return ScoredDecision(
        decision=Decision(
            id=decision_id,
            decision=f"Decision {decision_id}",
            scope=["scope-" + decision_id],
            constraints=[f"constraint-{decision_id}"],
            anti_patterns=[f"anti-{decision_id}"],
        ),
        score=score,
        matches={},
    )


def test_default_limit_is_three():
    assert DEFAULT_MAX_DECISIONS == 3


def test_injects_only_top_n():
    scored = [_scored(str(i), score=10 - i) for i in range(10)]
    out = format_decisions(scored, max_items=3)
    # Top 3 IDs are "0", "1", "2".
    for keep in ["Decision 0", "Decision 1", "Decision 2"]:
        assert keep in out
    for drop in ["Decision 5", "Decision 9"]:
        assert drop not in out


def test_skips_zero_score_items():
    scored = [_scored("a", score=2.0), _scored("b", score=0.0)]
    out = format_decisions(scored, max_items=3)
    assert "Decision a" in out
    assert "Decision b" not in out


def test_output_shows_decision_constraints_and_anti_patterns():
    scored = [_scored("a", score=5.0)]
    out = format_decisions(scored, max_items=3)
    assert "Decision a" in out
    assert "constraint-a" in out
    assert "anti-a" in out


def test_empty_input_returns_empty_string():
    assert format_decisions([], max_items=3) == ""


def test_deduplicates_by_id():
    """Same Decision id must not be injected twice."""
    scored = [_scored("a", score=5.0), _scored("a", score=4.0)]
    out = format_decisions(scored, max_items=3)
    assert out.count("Decision a") == 1
