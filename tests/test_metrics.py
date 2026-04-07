from app.reporting.metrics import compute_verdict, compute_per_user, compute_consistency


def test_verdict_signal_detected():
    """Both thresholds met → SIGNAL DETECTED."""
    unblinded = [
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 0.5, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -0.5, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u2"},
    ]
    v = compute_verdict(unblinded)
    assert v["win_rate"] == 3 / 5  # 60%
    assert v["avg_delta"] == (1 + 0.5 - 0.5 + 1 + 0) / 5  # 0.4
    assert v["verdict"] == "INCONCLUSIVE"  # win rate met but delta not


def test_verdict_clear_signal():
    unblinded = [{"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": f"u{i}"} for i in range(4)]
    unblinded.append({"true_winner_closeness": "default", "closeness_delta": -0.5, "user_id": "u5"})
    v = compute_verdict(unblinded)
    assert v["win_rate"] == 4 / 5  # 80%
    assert v["avg_delta"] == (4 * 1 + (-0.5)) / 5  # 0.7
    assert v["verdict"] == "SIGNAL DETECTED"


def test_verdict_no_signal():
    unblinded = [
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u3"},
    ]
    v = compute_verdict(unblinded)
    assert v["verdict"] == "NO SIGNAL"


def test_per_user_breakdown():
    unblinded = [
        {"true_winner_closeness": "mneme", "closeness_delta": 2, "user_id": "u1"},
        {"true_winner_closeness": "mneme", "closeness_delta": 1, "user_id": "u1"},
        {"true_winner_closeness": "default", "closeness_delta": -1, "user_id": "u2"},
        {"true_winner_closeness": "tie", "closeness_delta": 0, "user_id": "u2"},
    ]
    breakdown = compute_per_user(unblinded)
    assert breakdown["u1"]["wins"] == 2
    assert breakdown["u1"]["pattern"] == "dominant"
    assert breakdown["u2"]["wins"] == 0


def test_consistency_check():
    scores = [
        {"closeness_a": 5, "closeness_b": 2, "winner_closeness": "a"},  # consistent
        {"closeness_a": 2, "closeness_b": 4, "winner_closeness": "a"},  # inconsistent
        {"closeness_a": 3, "closeness_b": 3, "winner_closeness": "tie"},  # consistent
    ]
    result = compute_consistency(scores)
    assert result["agreement_rate"] == 2 / 3
    assert len(result["disagreements"]) == 1
    assert result["concern"] is True  # > 25% disagreement
