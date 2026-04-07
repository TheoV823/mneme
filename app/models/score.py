from app.utils.ids import new_id
from app.utils.timestamps import now_iso


def insert_score(db, *, assignment_id, closeness_a, closeness_b,
                 usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
                 winner_closeness, winner_usefulness, winner_distinctiveness,
                 preference, notes=None):
    score_id = new_id()
    created_at = now_iso()
    db.execute(
        """INSERT INTO scores (id, assignment_id, closeness_a, closeness_b,
           usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
           winner_closeness, winner_usefulness, winner_distinctiveness,
           preference, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (score_id, assignment_id, closeness_a, closeness_b,
         usefulness_a, usefulness_b, distinctiveness_a, distinctiveness_b,
         winner_closeness, winner_usefulness, winner_distinctiveness,
         preference, notes, created_at),
    )
    db.commit()
    return {"id": score_id, "assignment_id": assignment_id}


def get_score_for_assignment(db, assignment_id):
    row = db.execute("SELECT * FROM scores WHERE assignment_id = ?", (assignment_id,)).fetchone()
    return dict(row) if row else None
