import pytest
from unittest.mock import patch
from click.testing import CliRunner
from app.cli import compare_command, compare_stats_command
from app.models.user import insert_user
from app.models.comparison import get_comparisons_for_user


_FAKE_RUN_RESULT = {
    "output_a": "Default answer here.",
    "output_b": "Mneme answer here.",
    "option_a_mode": "default",
    "option_b_mode": "mneme",
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def user_id(db, app):
    with app.app_context():
        u = insert_user(db, name="Test User",
                        mneme_profile='{"decision_style": null}', source="test")
        return u["id"]


def test_compare_command_records_winner_b(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "How do you grow a product?"],
                input="b\n",
            )

    assert result.exit_code == 0, result.output
    assert "Option A" in result.output
    assert "Option B" in result.output

    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert len(rows) == 1
    assert rows[0]["winner"] == "b"
    assert rows[0]["preferred_mode"] == "mneme"


def test_compare_command_records_tie(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "Test prompt"],
                input="tie\n",
            )

    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "tie"
    assert rows[0]["preferred_mode"] is None


def test_compare_command_records_skip(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "Test prompt"],
                input="skip\n",
            )

    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "skip"
    assert rows[0]["preferred_mode"] is None


def test_compare_command_unknown_user_exits(runner, app):
    with app.app_context():
        result = runner.invoke(
            compare_command,
            ["--user-id", "nonexistent-id", "--prompt", "test"],
        )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_compare_command_invalid_choice_reprompts(runner, app, db, user_id):
    with app.app_context():
        with patch("app.cli.run_comparison", return_value=_FAKE_RUN_RESULT):
            result = runner.invoke(
                compare_command,
                ["--user-id", user_id, "--prompt", "test"],
                input="X\na\n",  # invalid then valid
            )
    assert result.exit_code == 0
    with app.app_context():
        rows = get_comparisons_for_user(db, user_id)
    assert rows[0]["winner"] == "a"
