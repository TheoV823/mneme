import pytest
from tests.conftest import *
from app.models.user import insert_user, get_user, list_users


def test_insert_and_get_user(db):
    user = insert_user(db, name="Alice", mneme_profile='{"style": "analytical"}', source="reddit")
    fetched = get_user(db, user["id"])
    assert fetched["name"] == "Alice"
    assert fetched["mneme_profile"] == '{"style": "analytical"}'
    assert fetched["source"] == "reddit"


def test_list_users(db):
    insert_user(db, name="Alice", mneme_profile='{}')
    insert_user(db, name="Bob", mneme_profile='{}')
    users = list_users(db)
    assert len(users) == 2


def test_insert_user_with_extra_context(db):
    user = insert_user(
        db,
        name="Test User",
        mneme_profile='{"decision_style": {"value": "analytical", "confidence": "medium", "sources": ["qa"]}}',
        extra_context="I prefer written briefs over meetings.",
        source="test",
    )
    assert user["extra_context"] == "I prefer written briefs over meetings."


def test_insert_user_extra_context_defaults_to_none(db):
    user = insert_user(db, name="No Context User", mneme_profile='{"x": 1}')
    assert user["extra_context"] is None


def test_get_user_includes_extra_context(db):
    inserted = insert_user(
        db, name="EC User", mneme_profile='{}', extra_context="some context"
    )
    fetched = get_user(db, inserted["id"])
    assert fetched["extra_context"] == "some context"
