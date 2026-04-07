from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db
from app.models.assignment import get_next_pending, mark_in_progress, mark_completed, mark_skipped, timeout_stale, count_completed, count_total
from app.models.score import insert_score, get_score_for_assignment
from app.models.run import get_run

scoring = Blueprint("scoring", __name__)


@scoring.before_request
def require_scorer():
    if request.endpoint == "scoring.login":
        return
    if "scorer_id" not in session or "scorer_type" not in session:
        return redirect(url_for("scoring.login"))


@scoring.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["scorer_id"] = request.form["scorer_id"]
        session["scorer_type"] = request.form.get("scorer_type", "layer1")
        return redirect(url_for("scoring.score"))
    return render_template("scoring/login.html")


@scoring.route("/score", methods=["GET"])
def score():
    db = get_db()
    scorer_type = session["scorer_type"]
    scorer_id = session["scorer_id"]

    # Timeout stale in_progress assignments
    timeout_stale(db)

    assignment = get_next_pending(db, scorer_type=scorer_type, scorer_id=scorer_id)
    if not assignment:
        completed = count_completed(db, scorer_type, scorer_id)
        return render_template("scoring/complete.html", completed=completed)

    mark_in_progress(db, assignment["id"])

    run = get_run(db, assignment["run_id"])

    # Prepare outputs based on A/B mapping and visual order
    if assignment["output_a_is"] == "mneme":
        output_a = run["output_mneme"]
        output_b = run["output_default"]
    else:
        output_a = run["output_default"]
        output_b = run["output_mneme"]

    # Visual order: which side is A?
    a_on_left = assignment["visual_order"] == "a_left"

    completed = count_completed(db, scorer_type, scorer_id)
    total = count_total(db, scorer_type, scorer_id)

    return render_template("scoring/score.html",
        assignment_id=assignment["id"],
        prompt_text=run["prompt_text"],
        output_a=output_a,
        output_b=output_b,
        a_on_left=a_on_left,
        completed=completed,
        total=total,
    )


@scoring.route("/score", methods=["POST"])
def submit_score():
    db = get_db()
    assignment_id = request.form["assignment_id"]

    # Prevent double-scoring
    existing = get_score_for_assignment(db, assignment_id)
    if existing:
        return redirect(url_for("scoring.score"))

    if "skip" in request.form:
        mark_skipped(db, assignment_id)
        return redirect(url_for("scoring.score"))

    # Validate score bounds
    score_fields = ["closeness_a", "closeness_b", "usefulness_a", "usefulness_b",
                    "distinctiveness_a", "distinctiveness_b"]
    for field in score_fields:
        val = int(request.form[field])
        if val < 1 or val > 5:
            flash(f"Invalid score for {field}: must be 1-5")
            return redirect(url_for("scoring.score"))

    winner_fields = ["winner_closeness", "winner_usefulness", "winner_distinctiveness", "preference"]
    for field in winner_fields:
        val = request.form[field]
        if val not in ("a", "b", "tie"):
            flash(f"Invalid winner for {field}: must be a, b, or tie")
            return redirect(url_for("scoring.score"))

    insert_score(
        db, assignment_id=assignment_id,
        closeness_a=int(request.form["closeness_a"]),
        closeness_b=int(request.form["closeness_b"]),
        usefulness_a=int(request.form["usefulness_a"]),
        usefulness_b=int(request.form["usefulness_b"]),
        distinctiveness_a=int(request.form["distinctiveness_a"]),
        distinctiveness_b=int(request.form["distinctiveness_b"]),
        winner_closeness=request.form["winner_closeness"],
        winner_usefulness=request.form["winner_usefulness"],
        winner_distinctiveness=request.form["winner_distinctiveness"],
        preference=request.form["preference"],
        notes=request.form.get("notes", ""),
    )
    mark_completed(db, assignment_id)

    # Log consistency check
    ca = int(request.form["closeness_a"])
    cb = int(request.form["closeness_b"])
    wc = request.form["winner_closeness"]
    if (ca > cb and wc == "b") or (cb > ca and wc == "a"):
        print(f"CONSISTENCY WARNING: assignment={assignment_id} closeness A={ca} B={cb} winner={wc}")

    return redirect(url_for("scoring.score"))
