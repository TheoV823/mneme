import pytest
from app.models.comparison import insert_comparison, get_comparisons_for_user, compute_win_rate
from app.models.user import insert_user


def _make_user(db):
    return insert_user(db, name="Alice", mneme_profile='{"decision_style": null}', source="test")


# --- insert_comparison + get_comparisons_for_user ---

def test_insert_comparison_and_retrieve(db):
    user = _make_user(db)
    c = insert_comparison(
        db,
        user_id=user["id"],
        prompt="How do you grow a product?",
        option_a_mode="default",
        option_b_mode="mneme",
        winner="b",
        preferred_mode="mneme",
    )
    assert c["id"]
    assert c["winner"] == "b"
    assert c["preferred_mode"] == "mneme"
    assert c["user_id"] == user["id"]

    rows = get_comparisons_for_user(db, user["id"])
    assert len(rows) == 1
    assert rows[0]["prompt"] == "How do you grow a product?"
    assert rows[0]["preferred_mode"] == "mneme"


def test_insert_comparison_tie_has_no_preferred_mode(db):
    user = _make_user(db)
    c = insert_comparison(
        db,
        user_id=user["id"],
        prompt="test prompt",
        option_a_mode="mneme",
        option_b_mode="default",
        winner="tie",
        preferred_mode=None,
    )
    assert c["winner"] == "tie"
    assert c["preferred_mode"] is None


def test_get_comparisons_for_user_empty(db):
    user = _make_user(db)
    rows = get_comparisons_for_user(db, user["id"])
    assert rows == []


def test_get_comparisons_for_user_multiple(db):
    user = _make_user(db)
    insert_comparison(db, user_id=user["id"], prompt="p1", option_a_mode="default",
                      option_b_mode="mneme", winner="a", preferred_mode="default")
    insert_comparison(db, user_id=user["id"], prompt="p2", option_a_mode="mneme",
                      option_b_mode="default", winner="a", preferred_mode="mneme")
    rows = get_comparisons_for_user(db, user["id"])
    assert len(rows) == 2


# --- compute_win_rate ---

def test_compute_win_rate_typical():
    comparisons = [
        {"winner": "a", "preferred_mode": "mneme"},
        {"winner": "b", "preferred_mode": "default"},
        {"winner": "a", "preferred_mode": "mneme"},
        {"winner": "tie", "preferred_mode": None},
        {"winner": "skip", "preferred_mode": None},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["mneme_wins"] == 2
    assert stats["default_wins"] == 1
    assert stats["ties"] == 1
    assert stats["skips"] == 1
    assert stats["total"] == 5
    assert abs(stats["win_rate"] - 2 / 3) < 0.001


def test_compute_win_rate_no_decisive():
    comparisons = [
        {"winner": "tie", "preferred_mode": None},
        {"winner": "skip", "preferred_mode": None},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["win_rate"] is None


def test_compute_win_rate_all_mneme():
    comparisons = [
        {"winner": "a", "preferred_mode": "mneme"},
        {"winner": "b", "preferred_mode": "mneme"},
    ]
    stats = compute_win_rate(comparisons)
    assert stats["win_rate"] == 1.0


def test_compute_win_rate_empty():
    stats = compute_win_rate([])
    assert stats["mneme_wins"] == 0
    assert stats["total"] == 0
    assert stats["win_rate"] is None
