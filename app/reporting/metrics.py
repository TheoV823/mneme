from collections import defaultdict

WIN_RATE_THRESHOLD = 0.60
DELTA_THRESHOLD = 0.5
CONSISTENCY_CONCERN_THRESHOLD = 0.25


def compute_verdict(unblinded, dimension="closeness"):
    total = len(unblinded)
    if total == 0:
        return {"wins": 0, "losses": 0, "ties": 0, "total": 0,
                "win_rate": 0, "avg_delta": 0, "verdict": "NO DATA"}

    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    wins = sum(1 for r in unblinded if r[winner_key] == "mneme")
    losses = sum(1 for r in unblinded if r[winner_key] == "default")
    ties = sum(1 for r in unblinded if r[winner_key] == "tie")
    win_rate = wins / total
    avg_delta = sum(r[delta_key] for r in unblinded) / total

    if win_rate >= WIN_RATE_THRESHOLD and avg_delta >= DELTA_THRESHOLD:
        verdict = "SIGNAL DETECTED"
    elif win_rate >= WIN_RATE_THRESHOLD or avg_delta >= DELTA_THRESHOLD:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "NO SIGNAL"

    return {
        "wins": wins, "losses": losses, "ties": ties, "total": total,
        "win_rate": win_rate, "avg_delta": avg_delta, "verdict": verdict,
    }


def compute_per_user(unblinded, dimension="closeness"):
    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    by_user = defaultdict(list)
    for r in unblinded:
        by_user[r["user_id"]].append(r)

    breakdown = {}
    for user_id, rows in by_user.items():
        total = len(rows)
        wins = sum(1 for r in rows if r[winner_key] == "mneme")
        losses = sum(1 for r in rows if r[winner_key] == "default")
        ties = sum(1 for r in rows if r[winner_key] == "tie")
        win_rate = wins / total if total > 0 else 0
        avg_delta = sum(r[delta_key] for r in rows) / total if total > 0 else 0

        if win_rate >= 0.8 and avg_delta >= 1.0:
            pattern = "dominant"
        elif win_rate >= 0.6 and avg_delta >= 0.5:
            pattern = "strong"
        elif win_rate >= 0.6 or avg_delta >= 0.5:
            pattern = "moderate"
        elif win_rate >= 0.4:
            pattern = "weak"
        else:
            pattern = "negative"

        breakdown[user_id] = {
            "wins": wins, "losses": losses, "ties": ties, "total": total,
            "win_rate": win_rate, "avg_delta": avg_delta, "pattern": pattern,
        }

    return breakdown


def compute_per_category(unblinded, dimension="closeness"):
    winner_key = f"true_winner_{dimension}"
    delta_key = f"{dimension}_delta"

    by_cat = defaultdict(list)
    for r in unblinded:
        by_cat[r.get("prompt_category", "unknown")].append(r)

    breakdown = {}
    for cat, rows in by_cat.items():
        total = len(rows)
        wins = sum(1 for r in rows if r[winner_key] == "mneme")
        win_rate = wins / total if total > 0 else 0
        avg_delta = sum(r[delta_key] for r in rows) / total if total > 0 else 0
        breakdown[cat] = {"wins": wins, "total": total, "win_rate": win_rate, "avg_delta": avg_delta}

    return breakdown


def compute_consistency(scores):
    """Check if winner picks agree with raw score direction."""
    total = len(scores)
    disagreements = []

    for i, s in enumerate(scores):
        a, b, w = s["closeness_a"], s["closeness_b"], s["winner_closeness"]
        if a > b and w == "b":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})
        elif b > a and w == "a":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})
        elif a == b and w != "tie":
            disagreements.append({"index": i, "a": a, "b": b, "winner": w})

    agreement_count = total - len(disagreements)
    agreement_rate = agreement_count / total if total > 0 else 1.0
    concern = (1 - agreement_rate) > CONSISTENCY_CONCERN_THRESHOLD

    return {
        "agreement_rate": agreement_rate,
        "disagreements": disagreements,
        "concern": concern,
    }
