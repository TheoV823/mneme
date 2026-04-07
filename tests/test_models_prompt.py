import pytest
from tests.conftest import *
from app.models.user import insert_user
from app.models.prompt import insert_prompt, get_prompts_for_user


def test_insert_shared_prompt(db):
    p = insert_prompt(db, text="Walk through a decision.", category="decision", scope="shared")
    assert p["scope"] == "shared"
    assert p["user_id"] is None


def test_get_prompts_for_user(db):
    user = insert_user(db, name="Alice", mneme_profile='{}')
    insert_prompt(db, text="Shared prompt 1", category="decision", scope="shared")
    insert_prompt(db, text="Shared prompt 2", category="strategy", scope="shared")
    insert_prompt(db, text="Shared prompt 3", category="creative", scope="shared")
    insert_prompt(db, text="Alice specific 1", category="analysis", scope="user_specific", user_id=user["id"])
    insert_prompt(db, text="Alice specific 2", category="personal", scope="user_specific", user_id=user["id"])

    prompts = get_prompts_for_user(db, user["id"])
    assert len(prompts) == 5
