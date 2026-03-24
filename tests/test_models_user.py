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
