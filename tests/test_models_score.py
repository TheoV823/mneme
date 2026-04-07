import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment, mark_in_progress
from app.models.score import insert_score, get_score_for_assignment


def _make_assignment(db):
    user = insert_user(db, name="Alice", mneme_profile='{}')
    prompt = insert_prompt(db, text="Test", category="decision", scope="shared")
    run = insert_run(
        db, user_id=user["id"], prompt_id=prompt["id"], prompt_text="Test",
        model="m", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="b", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="mneme", visual_order="a_left")
    mark_in_progress(db, a["id"])
    return a


def test_insert_and_get_score(db):
    a = _make_assignment(db)
    score = insert_score(
        db, assignment_id=a["id"],
        closeness_a=4, closeness_b=2,
        usefulness_a=3, usefulness_b=3,
        distinctiveness_a=5, distinctiveness_b=1,
        winner_closeness="a", winner_usefulness="tie", winner_distinctiveness="a",
        preference="a", notes="A felt more personal",
    )
    fetched = get_score_for_assignment(db, a["id"])
    assert fetched["closeness_a"] == 4
    assert fetched["preference"] == "a"
