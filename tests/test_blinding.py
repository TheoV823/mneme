import random
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment
from app.models.score import insert_score
from app.scoring.assigner import generate_assignments
from app.scoring.unblinder import unblind_scores


def _make_runs(db, count=50):
    """Create N runs for blinding tests."""
    user = insert_user(db, name="Alice", mneme_profile='{}')
    runs = []
    for i in range(count):
        p = insert_prompt(db, text=f"Prompt {i}", category="decision", scope="shared")
        r = insert_run(
            db, user_id=user["id"], prompt_id=p["id"], prompt_text=f"Prompt {i}",
            model="m", temperature=0.7, max_tokens=2048,
            output_default=f"default {i}", output_mneme=f"mneme {i}",
            system_prompt_default="s", system_prompt_mneme="s",
            profile_hash="h", batch_id="batch-test", protocol_version="v1",
            api_metadata_default="{}", api_metadata_mneme="{}",
            execution_order="default_first",
        )
        runs.append(r)
    return runs


def test_ab_randomization_is_balanced(db):
    """Over many assignments, A/B split should be approximately 50/50."""
    runs = _make_runs(db, count=200)
    assignments = generate_assignments(db, batch_id="batch-test",
                                        scorer_type="layer1", scorer_id="theo")

    mneme_as_a = sum(1 for a in assignments if a["output_a_is"] == "mneme")
    default_as_a = sum(1 for a in assignments if a["output_a_is"] == "default")

    # With 200 samples, expect 100 +/- 30 (very generous tolerance)
    assert 70 < mneme_as_a < 130, f"mneme_as_a={mneme_as_a}, expected ~100"
    assert 70 < default_as_a < 130, f"default_as_a={default_as_a}, expected ~100"


def test_visual_order_is_randomized(db):
    """Left/right placement should also be approximately 50/50."""
    runs = _make_runs(db, count=200)
    assignments = generate_assignments(db, batch_id="batch-test",
                                        scorer_type="layer1", scorer_id="theo")

    a_left = sum(1 for a in assignments if a["visual_order"] == "a_left")
    assert 70 < a_left < 130, f"a_left={a_left}, expected ~100"


def test_unblinding_maps_correctly(db):
    """Unblinding should correctly translate A/B winners to default/mneme."""
    user = insert_user(db, name="Bob", mneme_profile='{}')
    p = insert_prompt(db, text="Test", category="decision", scope="shared")
    r = insert_run(
        db, user_id=user["id"], prompt_id=p["id"], prompt_text="Test",
        model="m", temperature=0.7, max_tokens=2048,
        output_default="default out", output_mneme="mneme out",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-unblind", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )

    # output_a_is = "mneme", so A is mneme, B is default
    a = insert_assignment(db, run_id=r["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="mneme", visual_order="a_left")
    from app.models.assignment import mark_in_progress, mark_completed
    mark_in_progress(db, a["id"])
    insert_score(
        db, assignment_id=a["id"],
        closeness_a=5, closeness_b=2,
        usefulness_a=4, usefulness_b=3,
        distinctiveness_a=5, distinctiveness_b=1,
        winner_closeness="a", winner_usefulness="a", winner_distinctiveness="a",
        preference="a",
    )
    mark_completed(db, a["id"])

    results = unblind_scores(db, batch_id="batch-unblind")
    assert len(results) == 1
    r0 = results[0]
    # A was mneme and won → true winner is mneme
    assert r0["true_winner_closeness"] == "mneme"
    assert r0["true_winner_usefulness"] == "mneme"
    assert r0["true_winner_distinctiveness"] == "mneme"
    assert r0["true_preference"] == "mneme"
    # Delta: mneme score - default score = A score - B score (since A is mneme)
    assert r0["closeness_delta"] == 3  # 5 - 2
