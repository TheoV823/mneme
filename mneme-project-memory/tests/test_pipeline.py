"""End-to-end pipeline: load -> score -> inject top-N -> call LLM -> detect conflicts."""
from pathlib import Path

from mneme.pipeline import Pipeline, PipelineResult

EXAMPLE = Path(__file__).parent.parent / "examples" / "project_memory.json"


def test_pipeline_runs_in_dry_run():
    p = Pipeline(memory_path=EXAMPLE, dry_run=True, max_decisions=3)
    result = p.run("Should I switch storage to Postgres?")
    assert isinstance(result, PipelineResult)
    # Top-N cap respected.
    assert len(result.injected_decisions) <= 3
    # At least one decision injected for a storage-related query.
    assert len(result.injected_decisions) >= 1
    # The system prompt the adapter built must contain decision injection.
    assert "Mneme decisions applied" in result.system_prompt


def test_pipeline_surfaces_scores_in_debug():
    p = Pipeline(memory_path=EXAMPLE, dry_run=True)
    result = p.run("Should I switch storage to Postgres?")
    assert len(result.scored) >= 1
    # Top result's score must be >= any lower-ranked result.
    scores = [s.score for s in result.scored]
    assert scores == sorted(scores, reverse=True)


def test_pipeline_runs_conflict_detection_after_response():
    """Simulate a violating response by stubbing the adapter in dry_run+response."""
    p = Pipeline(memory_path=EXAMPLE, dry_run=True)
    # Inject a fake LLM response to exercise conflict detection.
    result = p.run(
        "Should I switch storage to Postgres?",
        _override_response="We recommend introducing Postgres next quarter.",
    )
    assert any(
        "postgres" in c.snippet.lower() for c in result.conflicts
    ), f"expected a postgres conflict, got {result.conflicts!r}"


def test_top_n_respected_even_when_more_match():
    p = Pipeline(memory_path=EXAMPLE, dry_run=True, max_decisions=1)
    result = p.run("storage retrieval agents postgres embeddings")
    assert len(result.injected_decisions) == 1
