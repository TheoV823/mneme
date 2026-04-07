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


def test_insert_user_with_extra_context_type(db):
    u = insert_user(db, name="Bob", mneme_profile="{}", extra_context="some notes",
                    extra_context_type="notes")
    assert u["extra_context_type"] == "notes"


def test_insert_user_extra_context_type_defaults_to_none(db):
    u = insert_user(db, name="Bob", mneme_profile="{}")
    assert u["extra_context_type"] is None


def test_add_user_command_stores_extra_context_type(app, db, tmp_path):
    """--extra-context-type is stored on the created user."""
    from click.testing import CliRunner
    from app.cli import add_user_command
    from unittest.mock import patch
    from app.models.user import list_users

    profile_file = tmp_path / "profile.json"
    profile_file.write_text('{"decision_style": "analytical"}')

    extra_file = tmp_path / "notes.txt"
    extra_file.write_text("I prefer async communication.")

    fake_ec_signals = {
        "decision_style": None, "risk_tolerance": None, "communication_style": None,
        "prioritization_rules": [], "constraints": [], "anti_patterns": [],
    }

    runner = CliRunner()
    with app.app_context():
        with patch("app.cli.extract_extra_context_signals", return_value=fake_ec_signals):
            result = runner.invoke(
                add_user_command,
                [str(profile_file), "--name", "Test",
                 "--extra-context-path", str(extra_file),
                 "--extra-context-type", "notes"],
            )

    assert result.exit_code == 0, result.output
    with app.app_context():
        users = list_users(db)
    assert len(users) == 1
    assert users[0]["extra_context_type"] == "notes"


def test_add_user_command_type_without_path_fails(app, tmp_path):
    """--extra-context-type without --extra-context-path is a usage error."""
    from click.testing import CliRunner
    from app.cli import add_user_command

    profile_file = tmp_path / "profile.json"
    profile_file.write_text('{"decision_style": "analytical"}')

    runner = CliRunner()
    with app.app_context():
        result = runner.invoke(
            add_user_command,
            [str(profile_file), "--name", "Test", "--extra-context-type", "notes"],
        )

    assert result.exit_code != 0
    assert "extra-context-path" in result.output.lower() or "requires" in result.output.lower()
