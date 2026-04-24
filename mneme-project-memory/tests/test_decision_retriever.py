"""Field-weighted relevance scoring over Decision records."""
from mneme.decision_retriever import DecisionRetriever, ScoredDecision
from mneme.schemas import Decision


def _retriever(decisions):
    return DecisionRetriever(decisions)


def test_scope_match_outweighs_content_match():
    decisions = [
        Decision(id="a", decision="Use JSON storage", scope=["storage"]),
        Decision(id="b", decision="Keep storage simple", scope=["other"]),
    ]
    ranked = _retriever(decisions).retrieve("How should I handle storage?")
    assert ranked[0].decision.id == "a"
    # Scope-match bonus = 2 beats the pure content-match of "storage" in title.
    assert ranked[0].score > ranked[1].score


def test_constraint_match_scores_higher_than_decision_text():
    decisions = [
        Decision(
            id="a",
            decision="Storage choice",
            constraints=["no postgres"],
        ),
        Decision(id="b", decision="postgres tuning"),
    ]
    ranked = _retriever(decisions).retrieve("should I use postgres?")
    # Constraint match (1.5x) + decision-text overlap must beat item b's
    # single decision-text hit.
    assert ranked[0].decision.id == "a"


def test_unrelated_query_scores_zero():
    decisions = [
        Decision(id="a", decision="Use JSON storage", scope=["storage"]),
    ]
    ranked = _retriever(decisions).retrieve("completely unrelated query about colors")
    assert ranked[0].score == 0


def test_score_components_recorded():
    """Debug output must explain which fields contributed."""
    decisions = [
        Decision(
            id="a",
            decision="Use JSON storage",
            scope=["storage"],
            constraints=["no postgres"],
        ),
    ]
    ranked = _retriever(decisions).retrieve("should I use postgres storage?")
    s = ranked[0]
    assert isinstance(s, ScoredDecision)
    assert s.matches["scope"] >= 1
    assert s.matches["constraints"] >= 1


def test_results_sorted_descending():
    decisions = [
        Decision(id="a", decision="Avoid postgres", constraints=["no postgres"]),
        Decision(id="b", decision="Something else entirely"),
    ]
    ranked = _retriever(decisions).retrieve("postgres")
    assert ranked[0].score >= ranked[-1].score
