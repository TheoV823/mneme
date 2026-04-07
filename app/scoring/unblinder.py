def _translate_winner(winner, output_a_is):
    if winner == "tie":
        return "tie"
    if output_a_is == "mneme":
        return "mneme" if winner == "a" else "default"
    else:
        return "default" if winner == "a" else "mneme"


def _compute_delta(score_a, score_b, output_a_is):
    """Return mneme_score - default_score."""
    if output_a_is == "mneme":
        return score_a - score_b
    else:
        return score_b - score_a


def unblind_scores(db, *, batch_id, scorer_type=None):
    query = """
        SELECT s.*, sa.output_a_is, sa.visual_order, sa.scorer_type, sa.scorer_id,
               r.user_id, r.prompt_id, r.prompt_text, r.batch_id, r.profile_hash,
               r.model, r.protocol_version,
               p.category as prompt_category
        FROM scores s
        JOIN scoring_assignments sa ON s.assignment_id = sa.id
        JOIN runs r ON sa.run_id = r.id
        JOIN prompts p ON r.prompt_id = p.id
        WHERE r.batch_id = ? AND sa.status = 'completed'
    """
    params = [batch_id]
    if scorer_type:
        query += " AND sa.scorer_type = ?"
        params.append(scorer_type)

    rows = db.execute(query, params).fetchall()

    results = []
    for row in rows:
        r = dict(row)
        a_is = r["output_a_is"]

        r["true_winner_closeness"] = _translate_winner(r["winner_closeness"], a_is)
        r["true_winner_usefulness"] = _translate_winner(r["winner_usefulness"], a_is)
        r["true_winner_distinctiveness"] = _translate_winner(r["winner_distinctiveness"], a_is)
        r["true_preference"] = _translate_winner(r["preference"], a_is)

        r["closeness_delta"] = _compute_delta(r["closeness_a"], r["closeness_b"], a_is)
        r["usefulness_delta"] = _compute_delta(r["usefulness_a"], r["usefulness_b"], a_is)
        r["distinctiveness_delta"] = _compute_delta(r["distinctiveness_a"], r["distinctiveness_b"], a_is)

        results.append(r)

    return results
