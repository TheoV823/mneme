import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt
from app.models.run import insert_run, get_run, run_exists


def _make_user_and_prompt(db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}')
    prompt = insert_prompt(db, text="Walk through a decision.", category="decision", scope="shared")
    return user, prompt


def test_insert_and_get_run(db):
    user, prompt = _make_user_and_prompt(db)
    run = insert_run(
        db,
        user_id=user["id"],
        prompt_id=prompt["id"],
        prompt_text=prompt["text"],
        model="test-model",
        temperature=0.7,
        max_tokens=2048,
        output_default="default response",
        output_mneme="mneme response",
        system_prompt_default="You are helpful.",
        system_prompt_mneme="You are helpful.\n<user_profile>...</user_profile>",
        profile_hash="abc123",
        batch_id="batch-001",
        protocol_version="v1",
        api_metadata_default='{"tokens": 100}',
        api_metadata_mneme='{"tokens": 120}',
        execution_order="default_first",
    )
    fetched = get_run(db, run["id"])
    assert fetched["output_default"] == "default response"
    assert fetched["output_mneme"] == "mneme response"
    assert fetched["profile_hash"] == "abc123"
    assert fetched["batch_id"] == "batch-001"


def test_run_exists_idempotency(db):
    user, prompt = _make_user_and_prompt(db)
    assert not run_exists(db, "batch-001", user["id"], prompt["id"], "test-model", "v1")

    insert_run(
        db, user_id=user["id"], prompt_id=prompt["id"], prompt_text=prompt["text"],
        model="test-model", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-001", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    assert run_exists(db, "batch-001", user["id"], prompt["id"], "test-model", "v1")


def test_duplicate_run_raises(db):
    user, prompt = _make_user_and_prompt(db)
    kwargs = dict(
        user_id=user["id"], prompt_id=prompt["id"], prompt_text=prompt["text"],
        model="test-model", temperature=0.7, max_tokens=2048,
        output_default="d", output_mneme="m",
        system_prompt_default="s", system_prompt_mneme="s",
        profile_hash="h", batch_id="batch-001", protocol_version="v1",
        api_metadata_default="{}", api_metadata_mneme="{}",
        execution_order="default_first",
    )
    insert_run(db, **kwargs)
    with pytest.raises(Exception):
        insert_run(db, **kwargs)
