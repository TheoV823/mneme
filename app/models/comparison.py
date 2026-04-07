from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_comparison(db, *, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode):
    row_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO comparison_results
           (id, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (row_id, user_id, prompt, option_a_mode, option_b_mode, winner, preferred_mode, created_at),
    )
    db.commit()
    return {
        "id": row_id,
        "user_id": user_id,
        "prompt": prompt,
        "option_a_mode": option_a_mode,
        "option_b_mode": option_b_mode,
        "winner": winner,
        "preferred_mode": preferred_mode,
        "created_at": created_at,
    }


def get_comparisons_for_user(db, user_id):
    rows = db.execute(
        "SELECT * FROM comparison_results WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def compute_win_rate(comparisons):
    """Return win-rate stats dict.

    win_rate = mneme_wins / (mneme_wins + default_wins).
    Ties and skips are excluded from the denominator but counted separately.
    Returns None for win_rate when there are no decisive comparisons.
    """
    mneme_wins = sum(1 for c in comparisons if c["preferred_mode"] == "mneme")
    default_wins = sum(1 for c in comparisons if c["preferred_mode"] == "default")
    ties = sum(1 for c in comparisons if c["winner"] == "tie")
    skips = sum(1 for c in comparisons if c["winner"] == "skip")
    total = len(comparisons)
    denominator = mneme_wins + default_wins
    win_rate = mneme_wins / denominator if denominator > 0 else None
    return {
        "mneme_wins": mneme_wins,
        "default_wins": default_wins,
        "ties": ties,
        "skips": skips,
        "total": total,
        "win_rate": win_rate,
    }
