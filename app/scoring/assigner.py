import random
from app.models.assignment import insert_assignment


def generate_assignments(db, *, batch_id, scorer_type, scorer_id):
    # Find runs in this batch that don't have assignments for this scorer
    rows = db.execute(
        """SELECT r.id FROM runs r
           WHERE r.batch_id = ?
           AND NOT EXISTS (
               SELECT 1 FROM scoring_assignments sa
               WHERE sa.run_id = r.id AND sa.scorer_type = ? AND sa.scorer_id = ?
           )""",
        (batch_id, scorer_type, scorer_id),
    ).fetchall()

    run_ids = [row["id"] for row in rows]
    random.shuffle(run_ids)

    assignments = []
    for run_id in run_ids:
        output_a_is = random.choice(["default", "mneme"])
        visual_order = random.choice(["a_left", "a_right"])
        a = insert_assignment(
            db, run_id=run_id, scorer_type=scorer_type, scorer_id=scorer_id,
            output_a_is=output_a_is, visual_order=visual_order,
        )
        assignments.append(a)

    return assignments
