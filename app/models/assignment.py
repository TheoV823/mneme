from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_assignment(db, *, run_id, scorer_type, scorer_id, output_a_is, visual_order):
    aid = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO scoring_assignments (id, run_id, scorer_type, scorer_id, output_a_is, visual_order, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (aid, run_id, scorer_type, scorer_id, output_a_is, visual_order, created_at),
    )
    db.commit()
    return {"id": aid, "run_id": run_id, "output_a_is": output_a_is, "visual_order": visual_order, "status": "pending"}


def get_next_pending(db, scorer_type, scorer_id):
    row = db.execute(
        """SELECT * FROM scoring_assignments
           WHERE scorer_type = ? AND scorer_id = ? AND status = 'pending'
           ORDER BY RANDOM() LIMIT 1""",
        (scorer_type, scorer_id),
    ).fetchone()
    return dict(row) if row else None


def mark_in_progress(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'in_progress' WHERE id = ?", (assignment_id,))
    db.commit()


def mark_completed(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'completed' WHERE id = ?", (assignment_id,))
    db.commit()


def mark_skipped(db, assignment_id):
    db.execute("UPDATE scoring_assignments SET status = 'skipped' WHERE id = ?", (assignment_id,))
    db.commit()


def timeout_stale(db, minutes=30):
    db.execute(
        """UPDATE scoring_assignments SET status = 'pending'
           WHERE status = 'in_progress'
           AND created_at < datetime('now', ? || ' minutes')""",
        (f"-{minutes}",),
    )
    db.commit()


def count_completed(db, scorer_type, scorer_id):
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM scoring_assignments WHERE scorer_type = ? AND scorer_id = ? AND status = 'completed'",
        (scorer_type, scorer_id),
    ).fetchone()
    return row["cnt"]


def count_total(db, scorer_type, scorer_id):
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM scoring_assignments WHERE scorer_type = ? AND scorer_id = ?",
        (scorer_type, scorer_id),
    ).fetchone()
    return row["cnt"]
