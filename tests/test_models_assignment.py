import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run
from app.models.assignment import insert_assignment, get_next_pending, mark_in_progress, mark_completed, mark_skipped, timeout_stale


def _make_run(db):
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
    return run


def test_insert_and_get_next(db):
    run = _make_run(db)
    insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                      output_a_is="mneme", visual_order="a_left")
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is not None
    assert pending["status"] == "pending"


def test_mark_in_progress(db):
    run = _make_run(db)
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="default", visual_order="a_right")
    mark_in_progress(db, a["id"])
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is None  # no more pending


def test_mark_skipped(db):
    run = _make_run(db)
    a = insert_assignment(db, run_id=run["id"], scorer_type="layer1", scorer_id="theo",
                          output_a_is="default", visual_order="a_left")
    mark_skipped(db, a["id"])
    pending = get_next_pending(db, scorer_type="layer1", scorer_id="theo")
    assert pending is None
